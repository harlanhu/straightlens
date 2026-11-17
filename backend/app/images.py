from dataclasses import dataclass
from pathlib import Path
from io import BytesIO
import warnings
from PIL import Image, ImageOps, ImageCms, UnidentifiedImageError
import numpy as np

MAX_BYTES=20*1024*1024
MAX_PIXELS=20_000_000
ALLOWED={'JPEG','PNG','WEBP'}

class ImageError(ValueError):
    def __init__(self,message,status=422):
        super().__init__(message)
        self.status=status

@dataclass
class ImageInfo:
    normalized_path: Path
    preview_path: Path
    estimate_path: Path
    width: int
    height: int
    format: str
    transparent: bool


def make_preview(source: Path, target: Path):
    with Image.open(source) as image:
        image.thumbnail((1600,1200))
        if image.mode=='RGBA':
            background=Image.new('RGB',image.size,(24,24,24))
            background.paste(image,mask=image.getchannel('A'))
            image=background
        image.convert('RGB').save(target,'JPEG',quality=90)


def normalize_image(source: Path, output_dir: Path) -> ImageInfo:
    if source.stat().st_size>MAX_BYTES:
        raise ImageError('图片超过 20 MiB，请选择较小的图片',413)
    output_dir.mkdir(parents=True,exist_ok=True)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(source) as original:
                fmt=original.format
                if fmt not in ALLOWED:
                    raise ImageError('仅支持 JPG、PNG、WebP 静态图片',415)
                if original.width*original.height>MAX_PIXELS:
                    raise ImageError('图片超过 2000 万像素',413)
                if getattr(original,'n_frames',1)!=1:
                    raise ImageError('暂不支持动画图片',415)
                original.load()
                image=ImageOps.exif_transpose(original)
                has_alpha='A' in image.getbands() or 'transparency' in image.info
                alpha=image.convert('RGBA').getchannel('A') if has_alpha else None
                icc=image.info.get('icc_profile')
                if icc:
                    try:
                        image=ImageCms.profileToProfile(image,ImageCms.ImageCmsProfile(BytesIO(icc)),ImageCms.createProfile('sRGB'),outputMode='RGB')
                    except (OSError,ValueError,ImageCms.PyCMSError):
                        image=image.convert('RGB')
                else:
                    image=image.convert('RGB')
                if alpha is not None:
                    image.putalpha(alpha)
    except ImageError:
        raise
    except (Image.DecompressionBombWarning,Image.DecompressionBombError) as exc:
        raise ImageError('图片像素数量过大',413) from exc
    except (OSError,ValueError,UnidentifiedImageError) as exc:
        raise ImageError('图片内容损坏或无法解码',422) from exc
    normalized=output_dir/'normalized.png'
    image.save(normalized)
    preview=output_dir/'original.jpg'
    make_preview(normalized,preview)
    estimate=image.copy()
    estimate.thumbnail((900,900))
    transparent=False
    if estimate.mode=='RGBA':
        alpha=np.asarray(estimate.getchannel('A'))
        transparent=bool(np.any(alpha<250))
        background=Image.new('RGB',estimate.size,(127,127,127))
        background.paste(estimate,mask=estimate.getchannel('A'))
        estimate=background
    estimate_path=output_dir/'estimate.png'
    estimate.convert('RGB').save(estimate_path)
    return ImageInfo(normalized,preview,estimate_path,image.width,image.height,fmt,transparent)
