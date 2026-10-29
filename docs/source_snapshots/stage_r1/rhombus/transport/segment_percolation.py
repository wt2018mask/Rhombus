"""Exploratory periodic minimax graphs with sampled interior edge energies.

Sampling does not establish continuous upper bounds or physical qualification.
"""
from collections import deque
from itertools import product
import numpy as np


def segment_percolation(field, lattice, evaluator, *, origin=(0, 0, 0), max_spacing_A, max_voxels=262144):
    v=np.asarray(field,float); shift=np.asarray(origin,float)
    if v.ndim!=3 or min(v.shape)<2 or v.size>max_voxels or not np.isfinite(v).all() or shift.shape!=(3,) or not np.isfinite(shift).all() or not np.isfinite(max_spacing_A) or max_spacing_A<=0:
        raise ValueError('finite bounded grid, origin and positive spacing required')
    shape=np.array(v.shape);n=v.size;idx=np.arange(n);cells=np.array(np.unravel_index(idx,v.shape)).T
    directions=[np.array(d) for d in product((-1,0,1),repeat=3) if d!=(0,0,0) and next(x for x in d if x)!=-1]
    edges=[]
    for direction in directions:
        raw=cells+direction; wrapped=raw%shape; image=raw//shape
        other=np.ravel_multi_index(wrapped.T,v.shape); length=np.linalg.norm(lattice.get_cartesian_coords(direction/shape))
        parts=max(1,int(np.ceil(length/max_spacing_A))); peak=np.maximum(v.ravel(),v.ravel()[other]).copy()
        for k in range(1,parts):
            frac=(cells+(k/parts)*direction)/shape+shift
            for start in range(0,n,2048):
                values=evaluator(lattice.get_cartesian_coords(frac[start:start+2048]))[0]
                peak[start:start+2048]=np.maximum(peak[start:start+2048],values)
        edges.append((peak,other,image))
    weights=np.concatenate([e[0] for e in edges]); order=np.argsort(weights,kind='stable')
    parent=np.arange(n);sizes=np.ones(n,int);offset=np.zeros((n,3),int);bases=[[] for _ in range(n)];forest=[[] for _ in range(n)];thresholds=[None]*3; witness=[None]*3
    def find(i):
        if parent[i]!=i:
            p=parent[i]; root,d=find(p);offset[i]+=d;parent[i]=root
        return parent[i],offset[i].copy()
    def add(root,vec,edge):
        if not np.any(vec) or len(bases[root])==3:return
        a=[x for x,_ in bases[root]]+[vec.tolist()]
        if np.linalg.matrix_rank(np.asarray(a,float))>len(bases[root]):bases[root].append((vec.tolist(),edge))
    for item in order:
        direction_index,a=divmod(int(item),n);b=int(edges[direction_index][1][a]);image=edges[direction_index][2][a]; ra,pa=find(a);rb,pb=find(b);delta=pa+image-pb
        if ra==rb:add(ra,delta,(a,b,image.copy()))
        else:
            forest[a].append((b,image.copy()));forest[b].append((a,-image.copy()))
            if sizes[ra]<sizes[rb]:ra,rb=rb,ra;delta=-delta
            parent[rb]=ra;offset[rb]=delta;sizes[ra]+=sizes[rb]
            for vec,edge in bases[rb]:add(ra,np.array(vec),edge)
        for k in range(len(bases[ra])):
            if thresholds[k] is None:thresholds[k]=float(weights[item]);witness[k]=list(bases[ra][:k+1])
        if thresholds[2] is not None:break
    def reconstruct(edge):
        a,b,closing=edge;prev={a:(None,np.zeros(3,int))};queue=deque([a])
        while queue and b not in prev:
            cur=queue.popleft()
            for nxt,im in forest[cur]:
                if nxt not in prev:prev[nxt]=(cur,im);queue.append(nxt)
        chain=[];cur=b
        while cur is not None:
            prior,im=prev[cur];chain.append((cur,im));cur=prior
        chain.reverse(); translation=np.zeros(3,int);path=[]
        for node,im in chain:
            translation+=im;path.append((cells[node]/shape+translation+shift).tolist())
        translation-=closing;path.append((cells[a]/shape+translation+shift).tolist())
        return {'fractional_path':path,'winding_vector':translation.tolist()}
    cycles=[reconstruct(e) for _,e in witness[2]] if witness[2] else []
    return {'schema':'sampled-edge-periodic-minimax-v1','minimum_energy_eV':float(v.min()),'thresholds_eV':dict(zip(('1D','2D','3D'),thresholds)),
            'barrier_3d_eV':thresholds[2]-float(v.min()) if thresholds[2] is not None else None,
            'cycles_3d':cycles,'grid_shape':v.shape,'edge_sample_spacing_A':float(max_spacing_A),
            'scope':'SAMPLED_NOT_CONTINUUM_GUARANTEE','qualification':'ABSTAIN'}
