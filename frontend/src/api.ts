export type Job = {
  id:string;status:'queued'|'running'|'succeeded'|'failed';stage:string;stages:string[];
  outcome?:'corrected'|'unchanged'|'failed'|'reversed';reason_code?:string;message:string;
  width?:number|null;height?:number|null;output_width?:number|null;output_height?:number|null;
  elapsed_seconds?:number|null;original_preview_url?:string|null;result_preview_url?:string|null;download_url?:string|null;
  original_image_url?:string|null;result_image_url?:string|null;
  kind?:'correction'|'reverse';parent_id?:string|null;reference_basis?:'cropped'|'uncropped'|null;
  uncropped_download_url?:string|null;uncropped_width?:number|null;uncropped_height?:number|null;
  can_reverse?:boolean;transform_version?:number|null;covered_fraction?:number|null;upload_preview_url?:string|null;upload_image_url?:string|null;
};
export type Basis='auto'|'cropped'|'uncropped';
export class ApiError extends Error{
  constructor(message:string,public code?:string,public referenceSizes?:Record<string,number[]>){super(message);}
}
async function response<T>(request:Promise<Response>):Promise<T>{
  const res=await request;
  if(!res.ok){const body=await res.json().catch(()=>({}));throw new ApiError(typeof body.detail==='string'?body.detail:'请求失败，请重新尝试。',body.code,body.reference_sizes);}
  return res.json();
}
export function uploadImage(file:File,signal:AbortSignal){
  const data=new FormData();data.append('image',file);
  return response<{id:string;status:'queued'}>(fetch('/api/jobs',{method:'POST',body:data,signal}));
}
export function getJob(id:string,signal:AbortSignal){return response<Job>(fetch(`/api/jobs/${id}`,{signal}));}
export function uploadReverse(parentId:string,file:File,basis:Basis,signal:AbortSignal){
  const data=new FormData();data.append('image',file);data.append('basis',basis);
  return response<{id:string;status:'queued'}>(fetch(`/api/jobs/${parentId}/reverse`,{method:'POST',body:data,signal}));
}
