"""Immutable, versioned record of the geometry actually used for correction."""
from dataclasses import dataclass,asdict
from pathlib import Path
import hashlib
import json
import numpy as np
from PIL import Image
from .ipol import CandidateConfig,CandidateResult
from .remap import correct_points,image_scale,valid_model


@dataclass(frozen=True)
class TransformSpec:
    version: int
    model: str
    coefficients: tuple[float,...]
    center: tuple[float,float]
    estimation_size: tuple[int,int]
    original_size: tuple[int,int]
    canvas_size: tuple[int,int]
    render_scale: float
    crop: tuple[int,int,int,int]
    orientation: str = 'exif_transposed'

    def __post_init__(self):
        if self.version!=1 or self.model not in ('pol','div') or self.orientation!='exif_transposed':
            raise ValueError('不支持的几何变换版本')
        for size in (self.estimation_size,self.original_size,self.canvas_size):
            if len(size)!=2 or any(type(n) is not int or n<=0 for n in size):raise ValueError('无效画布尺寸')
        if self.canvas_size!=self.original_size or np.prod(self.original_size)>20_000_000:raise ValueError('无效画布尺寸')
        if len(self.center)!=2 or len(self.coefficients) not in (2,3) or not np.isfinite((*self.center,*self.coefficients,self.render_scale)).all():raise ValueError('无效的几何参数')
        if len(self.crop)!=4 or any(type(n) is not int for n in self.crop):raise ValueError('无效裁切框')
        x0,y0,x1,y1=self.crop;w,h=self.canvas_size
        if not (0<=x0<x1<=w and 0<=y0<y1<=h):raise ValueError('裁切框越界')
        c=self.as_candidate()
        if not valid_model(c) or self.render_scale<=0 or not np.isclose(image_scale(c),self.render_scale,rtol=1e-10):raise ValueError('无效的几何映射或缩放')

    @classmethod
    def from_candidate(cls,candidate,original_size,crop):
        size=tuple(int(n) for n in original_size)
        return cls(1,candidate.config.model,tuple(candidate.coefficients),tuple(candidate.center),tuple(candidate.size),size,size,float(image_scale(candidate)),tuple(int(n) for n in crop))

    def as_candidate(self):
        return CandidateResult(CandidateConfig(self.model,.8),self.coefficients,self.center,self.estimation_size,[],Path('.'))

    @property
    def fingerprint(self):
        data=json.dumps(asdict(self),sort_keys=True,separators=(',',':'),allow_nan=False)
        return hashlib.sha256(data.encode()).hexdigest()

    def to_dict(self):
        return dict(asdict(self),fingerprint=self.fingerprint)

    def save(self,path):
        path=Path(path)
        temp=path.with_suffix('.tmp')
        temp.write_text(json.dumps(self.to_dict(),ensure_ascii=False,indent=2))
        temp.replace(path)

    @classmethod
    def from_dict(cls,data):
        required={'version','model','coefficients','center','estimation_size','original_size','canvas_size','render_scale','crop','orientation','fingerprint'}
        if set(data)!=required:raise ValueError('几何记录缺少字段或包含未知字段')
        fields={k:v for k,v in data.items() if k!='fingerprint'}
        for key in ('coefficients','center','estimation_size','original_size','canvas_size','crop'):fields[key]=tuple(fields[key])
        spec=cls(**fields)
        if spec.fingerprint!=data['fingerprint']:raise ValueError('几何记录校验失败')
        return spec


def original_to_canvas(points,spec):
    scales=np.array(spec.original_size,dtype=float)/spec.estimation_size
    corrected=correct_points(np.asarray(points,dtype=float)/scales,spec.as_candidate())
    return scales*(spec.center+(corrected-spec.center)/spec.render_scale)


def load_transform(job_dir:Path) -> TransformSpec:
    try:
        with Image.open(job_dir/'normalized.png') as original:size=original.size
        path=job_dir/'transform.json'
        if path.exists():
            spec=TransformSpec.from_dict(json.loads(path.read_text()))
        else:
            legacy=json.loads((job_dir/'model.json').read_text())
            c=CandidateResult(CandidateConfig(legacy['model'],.8),tuple(legacy['coefficients']),tuple(legacy['center']),tuple(legacy['estimation_size']),[],job_dir)
            spec=TransformSpec.from_candidate(c,size,tuple(legacy['crop']))
        if size!=spec.original_size:raise ValueError('原图尺寸与变换记录不一致')
        if (job_dir/'result.png').exists():
            with Image.open(job_dir/'result.png') as result:
                x0,y0,x1,y1=spec.crop
                if result.size!=(x1-x0,y1-y0):raise ValueError('校正结果与裁切记录不一致')
        return spec
    except (OSError,KeyError,TypeError,ValueError,json.JSONDecodeError) as exc:
        raise ValueError('校正记录不完整，请重新处理原图') from exc
