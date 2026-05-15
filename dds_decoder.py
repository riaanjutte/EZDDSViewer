import struct
import sys
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple

try:
    import texture2ddecoder as _t2d
    HAS_T2D = True
except ImportError:
    HAS_T2D = False

DDS_MAGIC = b'DDS '

DDPF_ALPHAPIXELS = 0x00000001
DDPF_ALPHA       = 0x00000002
DDPF_FOURCC      = 0x00000004
DDPF_RGB         = 0x00000040
DDPF_LUMINANCE   = 0x00020000
DDSCAPS2_CUBEMAP = 0x00000200

# DXGI format ID → (display name, has_alpha, bytes_per_block or 0 for uncompressed, bpp)
DXGI_FORMATS = {
    2:  ('R32G32B32A32_FLOAT', True,  0,  128),
    10: ('R16G16B16A16_FLOAT', True,  0,  64),
    28: ('R8G8B8A8_UNORM',     True,  0,  32),
    29: ('R8G8B8A8_UNORM_SRGB',True,  0,  32),
    56: ('R8_UNORM',           False, 0,  8),
    71: ('BC1',                False, 8,  0),
    72: ('BC1_SRGB',           False, 8,  0),
    74: ('BC2',                True,  16, 0),
    75: ('BC2_SRGB',           True,  16, 0),
    77: ('BC3',                True,  16, 0),
    78: ('BC3_SRGB',           True,  16, 0),
    80: ('BC4',                False, 8,  0),
    81: ('BC4_SNORM',          False, 8,  0),
    83: ('BC5',                False, 16, 0),
    84: ('BC5_SNORM',          False, 16, 0),
    95: ('BC6H_UF16',          False, 16, 0),
    96: ('BC6H_SF16',          False, 16, 0),
    98: ('BC7',                True,  16, 0),
    99: ('BC7_SRGB',           True,  16, 0),
}

# FourCC string → (base name, has_alpha, bytes_per_block)
FOURCC_MAP = {
    'DXT1': ('BC1',  False, 8),
    'DXT2': ('BC2',  True,  16),
    'DXT3': ('BC2',  True,  16),
    'DXT4': ('BC3',  True,  16),
    'DXT5': ('BC3',  True,  16),
    'ATI1': ('BC4',  False, 8),
    'BC4U': ('BC4',  False, 8),
    'BC4S': ('BC4',  False, 8),
    'ATI2': ('BC5',  False, 16),
    'BC5U': ('BC5',  False, 16),
    'BC5S': ('BC5',  False, 16),
    'BC6H': ('BC6H', False, 16),
    'BC7L': ('BC7',  True,  16),
    'BC7 ': ('BC7',  True,  16),
}

BC_CANONICAL = {
    'BC1': 'BC1', 'BC1_SRGB': 'BC1',
    'BC2': 'BC2', 'BC2_SRGB': 'BC2',
    'BC3': 'BC3', 'BC3_SRGB': 'BC3',
    'BC4': 'BC4', 'BC4_SNORM': 'BC4',
    'BC5': 'BC5', 'BC5_SNORM': 'BC5',
    'BC6H': 'BC6H', 'BC6H_UF16': 'BC6H', 'BC6H_SF16': 'BC6H',
    'BC7': 'BC7', 'BC7_SRGB': 'BC7',
}


@dataclass
class DDSInfo:
    width: int
    height: int
    mip_count: int
    format_name: str
    has_alpha: bool
    is_cubemap: bool
    file_size: int


def parse_dds(data: bytes) -> Tuple[DDSInfo, List[np.ndarray]]:
    if data[:4] != DDS_MAGIC:
        raise ValueError("Not a DDS file (invalid magic bytes)")

    off = 4
    (dw_size, dw_flags, height, width, pitch_or_linear,
     depth, mip_count) = struct.unpack_from('<7I', data, off)
    off += 28
    off += 44  # reserved[11]

    (pf_size, pf_flags, four_cc_int, rgb_bit_count,
     r_mask, g_mask, b_mask, a_mask) = struct.unpack_from('<8I', data, off)
    off += 32

    caps1, caps2 = struct.unpack_from('<II', data, off)
    off += 20  # caps1, caps2, caps3, caps4, reserved2

    is_cubemap = bool(caps2 & DDSCAPS2_CUBEMAP)
    if mip_count == 0:
        mip_count = 1

    block_bytes = 0
    bpp = 0

    if pf_flags & DDPF_FOURCC:
        four_cc = struct.pack('<I', four_cc_int).decode('ascii', errors='replace')
        if four_cc == 'DX10':
            dxgi_format = struct.unpack_from('<I', data, off)[0]
            off += 20  # dxgi_format, dim, misc_flag, array_size, misc_flags2
            entry = DXGI_FORMATS.get(dxgi_format)
            if entry is None:
                raise ValueError(f"Unsupported DXGI format: {dxgi_format}")
            fmt_name, has_alpha, block_bytes, bpp = entry
        else:
            four_cc = four_cc.rstrip('\x00')
            entry = FOURCC_MAP.get(four_cc)
            if entry is None:
                raise ValueError(f"Unsupported FourCC: {four_cc!r}")
            fmt_name, has_alpha, block_bytes = entry
            bpp = 0
    elif pf_flags & DDPF_RGB:
        has_alpha = bool(pf_flags & DDPF_ALPHAPIXELS)
        bpp = rgb_bit_count
        if bpp == 32:
            fmt_name = 'A8R8G8B8' if has_alpha else 'X8R8G8B8'
        elif bpp == 24:
            fmt_name = 'R8G8B8'
        elif bpp == 16:
            fmt_name = 'R5G6B5'
        else:
            fmt_name = f'RGB_{bpp}bpp'
    elif pf_flags & DDPF_LUMINANCE:
        has_alpha = bool(pf_flags & DDPF_ALPHAPIXELS)
        bpp = 16 if has_alpha else 8
        fmt_name = 'L8A8' if has_alpha else 'L8'
    elif pf_flags & DDPF_ALPHA:
        has_alpha = True
        bpp = 8
        fmt_name = 'A8'
    else:
        raise ValueError(f"Unknown DDS pixel format flags: {pf_flags:#010x}")

    info = DDSInfo(
        width=width, height=height, mip_count=mip_count,
        format_name=fmt_name, has_alpha=has_alpha,
        is_cubemap=is_cubemap, file_size=len(data),
    )

    mipmaps = []
    w, h = width, height
    data_off = off

    for _ in range(mip_count):
        if w == 0 or h == 0:
            break
        try:
            if block_bytes > 0:
                bx = max(1, (w + 3) // 4)
                by = max(1, (h + 3) // 4)
                n_bytes = bx * by * block_bytes
                img = _decode_bc(data, data_off, w, h, fmt_name, n_bytes)
            else:
                n_bytes = w * h * (bpp // 8)
                img = _decode_uncompressed(
                    data, data_off, w, h, bpp,
                    r_mask, g_mask, b_mask, a_mask, fmt_name,
                )
            mipmaps.append(img)
            data_off += n_bytes
        except Exception as exc:
            print(f"[dds_decoder] Stopped at mip {len(mipmaps)} "
                  f"({w}x{h}, {fmt_name}): {exc}", file=sys.stderr)
            break
        w = max(1, w >> 1)
        h = max(1, h >> 1)

    if not mipmaps:
        raise ValueError("Could not decode any mipmap surfaces")

    return info, mipmaps


def _decode_bc(data: bytes, offset: int, width: int, height: int,
               fmt: str, n_bytes: int) -> np.ndarray:
    base = BC_CANONICAL.get(fmt, fmt)
    block_data = data[offset: offset + n_bytes]

    if HAS_T2D:
        fn_map = {
            'BC1':  _t2d.decode_bc1,
            'BC3':  _t2d.decode_bc3,
            'BC4':  _t2d.decode_bc4,
            'BC5':  _t2d.decode_bc5,
            'BC6H': _t2d.decode_bc6,
            'BC7':  _t2d.decode_bc7,
        }
        fn = fn_map.get(base)
        if fn is not None:
            raw = fn(block_data, width, height)  # returns BGRA bytes
            arr = np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 4)
            return arr[:, :, [2, 1, 0, 3]].copy()  # BGRA → RGBA

    # Numpy fallback for BC1, BC2, BC3
    if base == 'BC1':
        return _bc1_numpy(block_data, width, height)
    if base == 'BC2':
        return _bc2_numpy(block_data, width, height)
    if base == 'BC3':
        return _bc3_numpy(block_data, width, height)

    # Unsupported: magenta placeholder
    img = np.zeros((height, width, 4), dtype=np.uint8)
    img[:, :, 0] = 255
    img[:, :, 2] = 255
    img[:, :, 3] = 255
    return img


def _decode_uncompressed(data: bytes, offset: int, width: int, height: int,
                          bpp: int, r_mask: int, g_mask: int, b_mask: int,
                          a_mask: int, fmt: str) -> np.ndarray:
    bpp_bytes = bpp // 8
    n_bytes = width * height * bpp_bytes
    img = np.zeros((height, width, 4), dtype=np.uint8)

    if bpp_bytes in (2, 4) and r_mask:
        # Generic mask-based decode
        if bpp_bytes == 4:
            raw = np.frombuffer(data[offset: offset + n_bytes], dtype='<u4').reshape(height, width)
        else:
            raw = np.frombuffer(data[offset: offset + n_bytes], dtype='<u2').reshape(height, width)

        def extract(mask):
            if not mask:
                return None
            shift = (mask & -mask).bit_length() - 1
            bits = bin(mask).count('1')
            vals = (raw >> shift) & ((1 << bits) - 1)
            return (vals * 255 // ((1 << bits) - 1)).astype(np.uint8)

        r = extract(r_mask)
        g = extract(g_mask)
        b = extract(b_mask)
        a = extract(a_mask)
        if r is not None: img[:, :, 0] = r
        if g is not None: img[:, :, 1] = g
        if b is not None: img[:, :, 2] = b
        img[:, :, 3] = a if a is not None else 255

    elif bpp_bytes == 3:
        raw = np.frombuffer(data[offset: offset + n_bytes], dtype=np.uint8).reshape(height, width, 3)
        img[:, :, 0] = raw[:, :, 2]  # BGR → RGB
        img[:, :, 1] = raw[:, :, 1]
        img[:, :, 2] = raw[:, :, 0]
        img[:, :, 3] = 255

    elif bpp_bytes == 1:
        raw = np.frombuffer(data[offset: offset + n_bytes], dtype=np.uint8).reshape(height, width)
        img[:, :, 0] = raw
        img[:, :, 1] = raw
        img[:, :, 2] = raw
        img[:, :, 3] = 255

    return img


# ── Numpy BC1/BC3 fallbacks ──────────────────────────────────────────────────

def _rgb565(v: np.ndarray) -> np.ndarray:
    r = ((v >> 11) & 0x1F) * 255 // 31
    g = ((v >> 5) & 0x3F) * 255 // 63
    b = (v & 0x1F) * 255 // 31
    return np.stack([r, g, b], axis=-1).astype(np.uint8)


def _blocks_to_image(block_rgba: np.ndarray, bx: int, by: int,
                     width: int, height: int) -> np.ndarray:
    """Reshape (n_blocks, 16, 4) → (height, width, 4)."""
    img = block_rgba.reshape(by, bx, 4, 4, 4)
    img = img.transpose(0, 2, 1, 3, 4).reshape(by * 4, bx * 4, 4)
    return np.ascontiguousarray(img[:height, :width])


def _decode_color_block(
    raw_color: np.ndarray, n: int
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Decode n BC1 color blocks (8 bytes each). Returns (colors, alpha, pix_idx)."""
    c0r = raw_color[:, 0].astype(np.uint16) | (raw_color[:, 1].astype(np.uint16) << 8)
    c1r = raw_color[:, 2].astype(np.uint16) | (raw_color[:, 3].astype(np.uint16) << 8)
    ib = raw_color[:, 4:8].astype(np.uint32)
    indices = ib[:, 0] | (ib[:, 1] << 8) | (ib[:, 2] << 16) | (ib[:, 3] << 24)

    c0 = _rgb565(c0r)
    c1 = _rgb565(c1r)
    c0i = c0.astype(np.int32)
    c1i = c1.astype(np.int32)

    colors = np.zeros((n, 4, 3), dtype=np.uint8)
    colors[:, 0] = c0
    colors[:, 1] = c1
    m4 = c0r > c1r
    m3 = ~m4
    colors[m4, 2] = ((c0i[m4] * 2 + c1i[m4]) // 3).astype(np.uint8)
    colors[m4, 3] = ((c0i[m4] + c1i[m4] * 2) // 3).astype(np.uint8)
    colors[m3, 2] = ((c0i[m3] + c1i[m3]) // 2).astype(np.uint8)
    colors[m3, 3] = 0

    # alpha for bc1 transparent pixels
    alpha = np.full((n, 4), 255, dtype=np.uint8)
    alpha[m3, 3] = 0

    pix_idx = np.zeros((n, 16), dtype=np.uint8)
    for i in range(16):
        pix_idx[:, i] = (indices >> (i * 2)) & 3

    return colors, alpha, pix_idx


def _bc1_numpy(data: bytes, width: int, height: int) -> np.ndarray:
    bx = max(1, (width + 3) // 4)
    by = max(1, (height + 3) // 4)
    n = bx * by
    raw = np.frombuffer(data[: n * 8], dtype=np.uint8).reshape(n, 8)
    colors, alpha, pix_idx = _decode_color_block(raw, n)

    block_rgb = colors[np.arange(n)[:, None], pix_idx]        # (n, 16, 3)
    block_a   = alpha[np.arange(n)[:, None], pix_idx][:, :, None]  # (n, 16, 1)
    block_rgba = np.concatenate([block_rgb, block_a], axis=2)  # (n, 16, 4)
    return _blocks_to_image(block_rgba, bx, by, width, height)


def _decode_bc4_channel(raw8: np.ndarray, n: int) -> np.ndarray:
    """Decode n BC4 alpha blocks (8 bytes). Returns (n, 16) uint8."""
    a0 = raw8[:, 0].astype(np.int32)
    a1 = raw8[:, 1].astype(np.int32)
    bits = np.zeros(n, dtype=np.int64)
    for b in range(6):
        bits |= raw8[:, 2 + b].astype(np.int64) << (b * 8)

    idx = np.zeros((n, 16), dtype=np.uint8)
    for i in range(16):
        idx[:, i] = (bits >> (i * 3)) & 7

    t = np.zeros((n, 8), dtype=np.int32)
    t[:, 0] = a0
    t[:, 1] = a1
    m6 = a0 > a1
    m4 = ~m6
    for i in range(2, 8):
        t[m6, i] = ((8 - i) * a0[m6] + (i - 1) * a1[m6]) // 7
    for i in range(2, 6):
        t[m4, i] = ((6 - i) * a0[m4] + (i - 1) * a1[m4]) // 5
    t[m4, 6] = 0
    t[m4, 7] = 255

    return t[np.arange(n)[:, None], idx].clip(0, 255).astype(np.uint8)


def _bc2_numpy(data: bytes, width: int, height: int) -> np.ndarray:
    """BC2/DXT3: explicit 4-bit alpha + BC1 color (always 4-color mode)."""
    bx = max(1, (width + 3) // 4)
    by = max(1, (height + 3) // 4)
    n = bx * by
    raw = np.frombuffer(data[: n * 16], dtype=np.uint8).reshape(n, 16)

    # 8 bytes of explicit 4-bit alpha: low nibble first, then high nibble
    ab = raw[:, :8]
    alpha = np.empty((n, 16), dtype=np.uint8)
    alpha[:, 0::2] = (ab & 0xF) * 17        # scale 0-15 → 0-255
    alpha[:, 1::2] = ((ab >> 4) & 0xF) * 17

    colors, _, pix_idx = _decode_color_block(raw[:, 8:], n)
    block_rgb  = colors[np.arange(n)[:, None], pix_idx]
    block_rgba = np.concatenate([block_rgb, alpha[:, :, None]], axis=2)
    return _blocks_to_image(block_rgba, bx, by, width, height)


def _bc3_numpy(data: bytes, width: int, height: int) -> np.ndarray:
    bx = max(1, (width + 3) // 4)
    by = max(1, (height + 3) // 4)
    n = bx * by
    raw = np.frombuffer(data[: n * 16], dtype=np.uint8).reshape(n, 16)

    alpha = _decode_bc4_channel(raw[:, :8], n)          # (n, 16)
    colors, _, pix_idx = _decode_color_block(raw[:, 8:], n)

    block_rgb  = colors[np.arange(n)[:, None], pix_idx]       # (n, 16, 3)
    block_rgba = np.concatenate([block_rgb, alpha[:, :, None]], axis=2)
    return _blocks_to_image(block_rgba, bx, by, width, height)
