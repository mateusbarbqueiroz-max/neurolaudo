"""WMH-SynthSeg com pouca memória: a mesma rede e os mesmos pesos, calculada por fatias. Uso em pesquisa.

O WMH-SynthSeg do FreeSurfer 8.2 (Laso e colaboradores, 2024) segmenta lesões de substância branca e as
estruturas do encéfalo em FLAIR (ou outro contraste). O programa original calcula a rede inteira de uma vez e
precisou de mais de 16 GB no servidor do GitHub. Aqui cada convolução é feita em fatias de poucos cortes, com
um corte de borda de cada lado; a normalização de grupo (GroupNorm) usa a média e a variância do volume
inteiro, como na rede original, calculadas antes das fatias. O resultado tem de ser o mesmo, a menos de
arredondamento; `--conferir` compara com a rede original em volumes pequenos (com `--i`, também num bloco
do exame) e `--original` roda o inference.py original inteiro, só com a rede trocada por esta.

Uso:
  python wmh_lowmem.py --codigo PASTA --modelo ARQ.pth --conferir [--i FLAIR.nii.gz]
  python wmh_lowmem.py --codigo PASTA --modelo ARQ.pth --i FLAIR.nii.gz --o SEG.nii.gz --csv VOL.csv [--threads N]
  python wmh_lowmem.py --codigo PASTA --modelo ARQ.pth --original --i FLAIR.nii.gz --o SEG.nii.gz --csv VOL.csv

PASTA: a pasta WMHSynthSeg do FreeSurfer 8.2 (inference.py, utils.py, unet3d/), de onde vêm a rede e o
pré-processamento, sem mudança.
"""
from __future__ import annotations

import argparse
import math
import resource
import sys
import time

import numpy as np

LABELS = [0, 14, 15, 16, 24, 77, 85, 2, 3, 4, 7, 8, 10, 11, 12, 13, 17, 18, 26, 28, 41, 42, 43, 46,
          47, 49, 50, 51, 52, 53, 54, 58, 60]
NAMES = ['background', '3rd-ventricle', '4th-ventricle', 'brainstem', 'extracerebral_CSF', 'WMH', 'optic-chiasm',
         'left-white-matter', 'left-cortex', 'left-lateral-ventricle', 'left-cerebellum-white-matter',
         'left-cerebellum-cortex', 'left-thalamus', 'left-caudate', 'left-putamen', 'left-pallidum',
         'left-hippocampus', 'left-amygdala', 'left-accumbens', 'left-ventral-DC',
         'right-white-matter', 'right-cortex', 'right-lateral-ventricle', 'right-cerebellum-white-matter',
         'right-cerebellum-cortex', 'right-thalamus', 'right-caudate', 'right-putamen', 'right-pallidum',
         'right-hippocampus', 'right-amygdala', 'right-accumbens', 'right-ventral-DC']
N_LABELS = len(LABELS)
N_NEUTRAL = 7
SLOPE = 0.01                       # nn.LeakyReLU() padrão, usado pela rede ("gcl")
COLUMN_BUDGET = 256 * 1024 ** 2    # bytes por chamada de convolução, para a fatia não pesar


def peak_gb() -> float:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / 1024 ** 3 if sys.platform == "darwin" else peak / 1024 ** 2


# MARK: fontes de dados por fatias

class Plain:
    """Um tensor guardado (C, D, H, W)."""

    def __init__(self, t):
        self.t = t

    @property
    def shape(self):
        return tuple(self.t.shape)

    def get(self, a, b):
        return self.t[:, a:b]

    def channel_sums(self, torch):
        """Soma e soma dos quadrados de cada canal, em precisão dupla, e quantos voxels por canal."""
        c = self.t.shape[0]
        sums = torch.zeros(c, dtype=torch.float64)
        squares = torch.zeros(c, dtype=torch.float64)
        for k in range(c):
            ch = self.t[k].double()
            sums[k] = ch.sum()
            squares[k] = (ch * ch).sum()
        return sums, squares, self.t[0].numel()


class Concat:
    """cat((skip, up(low)), dim=canais) sem montar o volume inteiro: `low` tem metade da resolução, e `up` é a
    interpolação "nearest" para o dobro, que repete cada voxel 8 vezes."""

    def __init__(self, skip, low):
        self.skip, self.low = skip, low
        assert tuple(2 * s for s in low.shape[1:]) == tuple(skip.shape[1:]), (skip.shape, low.shape)

    @property
    def shape(self):
        return (self.skip.shape[0] + self.low.shape[0],) + tuple(self.skip.shape[1:])

    def get(self, a, b):
        import torch
        lo = self.low[:, a // 2:(b - 1) // 2 + 1]
        up = lo.repeat_interleave(2, dim=1)[:, a - 2 * (a // 2):a - 2 * (a // 2) + (b - a)]
        up = up.repeat_interleave(2, dim=2).repeat_interleave(2, dim=3)
        return torch.cat((self.skip[:, a:b], up), dim=0)

    def channel_sums(self, torch):
        s1, q1, n = Plain(self.skip).channel_sums(torch)
        s2, q2, _ = Plain(self.low).channel_sums(torch)
        return torch.cat((s1, 8 * s2)), torch.cat((q1, 8 * q2)), n


# MARK: convoluções por fatias

def affine(torch, source, gn):
    """Escala e deslocamento por canal equivalentes à GroupNorm com a estatística do volume inteiro."""
    sums, squares, n = source.channel_sums(torch)
    c = sums.shape[0]
    g = gn.num_groups
    per = c // g
    gsum = sums.view(g, per).sum(1)
    gsq = squares.view(g, per).sum(1)
    count = n * per
    mean = gsum / count
    var = (gsq / count - mean * mean).clamp_min(0)
    rstd = 1.0 / torch.sqrt(var + gn.eps)
    mean_c = mean.repeat_interleave(per)
    rstd_c = rstd.repeat_interleave(per)
    scale = rstd_c * gn.weight.double()
    shift = gn.bias.double() - mean_c * scale
    return scale.float().view(c, 1, 1, 1), shift.float().view(c, 1, 1, 1)


def slab_for(c_in, h, w):
    return max(1, int(COLUMN_BUDGET // (c_in * 27 * h * w * 4)))


def single_conv(torch, source, sc, consumer, slab=None):
    """GroupNorm (volume inteiro) → Conv3d 3×3×3 sem viés → LeakyReLU, fatia a fatia. `consumer(z0, z1, y)`."""
    F = torch.nn.functional
    scale, shift = affine(torch, source, sc.groupnorm)
    c, d, h, w = source.shape
    slab = slab or slab_for(c, h, w)
    weight = sc.conv.weight
    for z0 in range(0, d, slab):
        z1 = min(d, z0 + slab)
        a, b = max(0, z0 - 1), min(d, z1 + 1)
        xs = source.get(a, b) * scale + shift
        xs = F.pad(xs, (1, 1, 1, 1, 1 if a == z0 else 0, 1 if b == z1 else 0))
        y = F.conv3d(xs[None], weight)[0]
        consumer(z0, z1, F.leaky_relu(y, SLOPE))


def double_conv(torch, source, block, last=None):
    """DoubleConv por fatias. `source` pode vir numa lista de um item: assim a entrada é solta da memória logo
    depois da primeira convolução. `last`: função que recebe as fatias da saída em vez de guardá-la."""
    if isinstance(source, list):
        source = source.pop()
    c, d, h, w = source.shape
    sc1, sc2 = block.SingleConv1, block.SingleConv2
    mid = torch.empty((sc1.conv.out_channels, d, h, w))
    single_conv(torch, source, sc1, lambda z0, z1, y: mid[:, z0:z1].copy_(y))
    source = None
    if last is not None:
        single_conv(torch, Plain(mid), sc2, last)
        return None
    out = torch.empty((sc2.conv.out_channels, d, h, w))
    single_conv(torch, Plain(mid), sc2, lambda z0, z1, y: out[:, z0:z1].copy_(y))
    return out


def logits(torch, model, volume):
    """Mesmo resultado de model(volume[None, None])[0, :N_LABELS], com pouca memória. volume: (D, H, W)."""
    F = torch.nn.functional
    features = []
    current = volume[None].float()
    for i, encoder in enumerate(model.encoders):
        if i > 0:
            current = F.max_pool3d(current[None], 2)[0]
        current = double_conv(torch, Plain(current), encoder.basic_module)
        features.insert(0, current)
    x = features.pop(0)
    skips = features
    final_w = model.final_conv.weight[:N_LABELS]
    final_b = model.final_conv.bias[:N_LABELS]
    out = None
    for k, decoder in enumerate(model.decoders):
        holder = [Concat(skips[k], x)]
        d, h, w = skips[k].shape[1:]
        skips[k] = None     # a entrada fica só no `holder`, e sai da memória depois da primeira convolução
        x = None
        if k < len(model.decoders) - 1:
            x = double_conv(torch, holder, decoder.basic_module)
        else:
            out = torch.empty((N_LABELS, d, h, w))

            def write(z0, z1, y):
                out[:, z0:z1] = F.conv3d(y[None], final_w, final_b)[0]

            double_conv(torch, holder, decoder.basic_module, last=write)
    return out


# MARK: o fluxo do inference.py original, com a rede trocada pela versão por fatias

def figure(path, image, seg, title):
    """Cortes axiais do FLAIR (1 mm, alinhado) com as lesões em vermelho, em convenção radiológica."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    brain = np.argwhere(seg > 0)
    k_low, k_high = brain[:, 2].min(), brain[:, 2].max()
    ks = np.linspace(k_low + 0.35 * (k_high - k_low), k_low + 0.85 * (k_high - k_low), 8).astype(int)
    top = np.percentile(image[seg > 0], 99.5)
    fig, axes = plt.subplots(2, 4, figsize=(12, 7), facecolor="black")
    for ax, k in zip(axes.ravel(), ks):
        slice_ = np.clip(image[:, :, k] / top, 0, 1)[::-1, ::-1].T
        lesion = (seg[:, :, k] == 77)[::-1, ::-1].T
        rgb = np.stack([slice_] * 3, axis=-1)
        rgb[lesion] = 0.35 * rgb[lesion] + 0.65 * np.array([1.0, 0.1, 0.1])
        ax.imshow(rgb, interpolation="nearest")
        ax.set_title(f"corte {k}", color="white", fontsize=8)
        ax.axis("off")
    fig.suptitle(title, color="white", fontsize=10)
    fig.savefig(path, dpi=80, facecolor="black")
    plt.close(fig)


def prepare(torch, utils, path_in):
    """Leitura, alinhamento, normalização para [0, 1] e reamostragem para 1 mm, como no inference.py original."""
    image, aff = utils.MRIread(path_in)
    image_torch = torch.tensor(np.squeeze(image).astype(float))
    while len(image_torch.shape) > 3:
        image_torch = image_torch.mean(dim=-1)
    image_torch, aff2 = utils.align_volume_to_ref(image_torch, aff, aff_ref=np.eye(4), return_aff=True, n_dims=3)
    image_torch = image_torch / torch.max(image_torch)
    voxsize = np.sqrt(np.sum(aff2 ** 2, axis=0))[:-1]
    factors = voxsize / np.array([1.0, 1.0, 1.0])
    upscaled = utils.myzoom_torch(image_torch, factors, device=torch.device("cpu"))
    aff_up = aff2.copy()
    for j in range(3):
        aff_up[:-1, j] = aff_up[:-1, j] / factors[j]
    aff_up[:-1, -1] = aff_up[:-1, -1] - np.matmul(aff_up[:-1, :-1], 0.5 * (factors - 1))
    return upscaled, aff_up


def segment(torch, model, utils, path_in, path_out, csv_path, figure_path=None, json_path=None):
    upscaled, aff_up = prepare(torch, utils, path_in)

    # Recorte de 192 × 224 × 192 centrado no encéfalo, como no original com --crop: passo preliminar no volume
    # centrado, centro de massa de tálamos e ventrículos laterais.
    size = (192, 224, 192)
    cuboid = torch.zeros(size)
    src, dst = [], []
    for n, s in zip(upscaled.shape, size):
        if n <= s:
            o = int(np.floor((s - n) / 2))
            src.append((0, n))
            dst.append((o, o + n))
        else:
            i = int(np.floor((n - s) / 2))
            src.append((i, i + s))
            dst.append((0, s))
    cuboid[dst[0][0]:dst[0][1], dst[1][0]:dst[1][1], dst[2][0]:dst[2][1]] = \
        upscaled[src[0][0]:src[0][1], src[1][0]:src[1][1], src[2][0]:src[2][1]]
    started = time.monotonic()
    pred = logits(torch, model, cuboid)
    seg_p = torch.softmax(pred, dim=0)
    del pred
    p = sum(seg_p[LABELS.index(lab)] for lab in (10, 49, 4, 43))
    del seg_p
    den = torch.sum(p)
    grid = [torch.arange(s, dtype=torch.float32) for s in size]
    gi, gj, gk = torch.meshgrid(*grid, indexing="ij")
    centre = [torch.sum(p * g) / den for g in (gi, gj, gk)]
    del gi, gj, gk, p
    offsets = [max(0, int(c + s0[0] - s / 2)) for c, s0, s in zip(centre, src, size)]
    ic, jc, kc = offsets
    upscaled = upscaled[ic:, jc:, kc:]
    aff_up[:-1, -1] = aff_up[:-1, -1] + np.matmul(aff_up[:-1, :-1], np.array([ic, jc, kc]))
    upscaled = upscaled[:min(192, upscaled.shape[0]), :min(224, upscaled.shape[1]), :min(192, upscaled.shape[2])]
    first_pass = time.monotonic() - started

    s0, s1, s2 = upscaled.shape
    padded = torch.zeros(tuple((np.ceil(np.array(upscaled.shape) / 32.0) * 32).astype(int)))
    padded[:s0, :s1, :s2] = upscaled
    started = time.monotonic()
    probs = torch.softmax(logits(torch, model, padded)[:, :s0, :s1, :s2], dim=0)
    nlat = int((N_LABELS - N_NEUTRAL) / 2.0)
    vflip = np.concatenate([np.arange(N_NEUTRAL), np.arange(N_NEUTRAL + nlat, N_LABELS),
                            np.arange(N_NEUTRAL, N_NEUTRAL + nlat)])
    # Segunda passada com o volume espelhado; troca os rótulos de esquerda e direita. Uma cópia por vez.
    other = logits(torch, model, torch.flip(padded, [0]))
    other = other[torch.as_tensor(vflip)]
    other = torch.flip(other, [1])[:, :s0, :s1, :s2]
    probs.add_(torch.softmax(other, dim=0))
    del other
    probs.mul_(0.5)
    second_pass = time.monotonic() - started

    seg = torch.as_tensor(LABELS)[torch.argmax(probs, 0)].numpy().astype(np.int32)
    vols = np.array([probs[k].double().sum().item() for k in range(N_LABELS)])
    utils.MRIwrite(seg, aff_up, path_out)
    if csv_path:
        with open(csv_path, "w") as fh:
            fh.write("Input-file,Intracranial-volume," + ",".join(f"{n}({lab})" for n, lab in zip(NAMES, LABELS) if lab) + "\n")
            fh.write(f"{path_out},{np.sum(vols[1:])}," + ",".join(str(v) for v, lab in zip(vols, LABELS) if lab) + "\n")
    wmh = vols[LABELS.index(77)] / 1000
    from scipy import ndimage
    mask = seg == 77
    components, count = ndimage.label(mask, structure=np.ones((3, 3, 3)))
    sizes = np.sort(np.bincount(components.ravel())[1:])[::-1] if count else np.array([0])
    print(f"lesões rotuladas: {mask.sum() / 1000:.2f} mL em {count} focos (maiores: {', '.join(str(v) for v in sizes[:5])} voxels; "
          f"focos de até 3 voxels: {int((sizes <= 3).sum())})", flush=True)
    if json_path:
        import json
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump({"lesoes_ml": round(float(wmh), 3), "lesoes_rotuladas_ml": round(float(mask.sum()) / 1000, 3),
                       "focos": int(count), "intracraniano_ml": round(float(np.sum(vols[1:])) / 1000, 1),
                       "tempo_s": round(first_pass + second_pass, 1), "memoria_gb": round(peak_gb(), 2)}, fh)
    if figure_path:
        figure(figure_path, upscaled.numpy(), seg, f"{path_in.split('/')[-1]}: lesões {wmh:.2f} mL (soma das probabilidades), "
               f"{mask.sum() / 1000:.2f} mL rotuladas")
    print(f"lesões (WMH): {wmh:.2f} mL; volume intracraniano {np.sum(vols[1:]) / 1000:.1f} mL; "
          f"passo preliminar {first_pass:.0f} s, segmentação {second_pass:.0f} s; memória máxima {peak_gb():.1f} GB", flush=True)
    return wmh


def real_block(torch, utils, path_in, size=(128, 160, 128)):
    """Bloco do exame (já como a rede o recebe) centrado no centro de massa da imagem; zeros onde faltar."""
    from scipy import ndimage
    upscaled, _ = prepare(torch, utils, path_in)
    centre = ndimage.center_of_mass(upscaled.numpy())
    block = torch.zeros(size)
    src, dst = [], []
    for n, s, c in zip(upscaled.shape, size, centre):
        a = int(min(max(0, round(c) - s // 2), max(0, n - s)))
        b = min(n, a + s)
        src.append(slice(a, b))
        dst.append(slice(0, b - a))
    block[tuple(dst)] = upscaled[tuple(src)]
    return block


def check(torch, model, utils=None, path_in=None):
    """Compara com a rede original em volumes pequenos (a original cabe na memória neles): dois de ruído e, com
    `path_in`, um bloco do exame de verdade."""
    gen = torch.Generator().manual_seed(7)
    worst = 0.0
    volumes = []
    for shape in ((64, 96, 64), (96, 64, 96)):
        volume = torch.rand(shape, generator=gen)
        volume[:8] = 0                      # fundo de zeros, como o enchimento do volume real
        volumes.append(("ruído", volume))
    if path_in:
        volumes.append(("exame", real_block(torch, utils, path_in)))
    for kind, volume in volumes:
        shape = tuple(volume.shape)
        with torch.no_grad():
            reference = model(volume[None, None])[0, :N_LABELS]
            mine = logits(torch, model, volume)
        diff = (reference - mine).abs().max().item()
        scale = reference.abs().max().item()
        same = (reference.argmax(0) == mine.argmax(0)).float().mean().item()
        worst = max(worst, diff / max(1.0, scale))      # relativa: o arredondamento cresce com a escala das saídas
        print(f"conferência {shape} ({kind}): maior diferença nas saídas {diff:.2e} (escala {scale:.1f}); "
              f"mesmo rótulo em {100 * same:.4f} % dos voxels", flush=True)
        if kind == "exame":
            wmh = LABELS.index(77)
            a, b = reference.argmax(0) == wmh, mine.argmax(0) == wmh
            print(f"lesões no bloco do exame: rede original {int(a.sum())} voxels, por fatias {int(b.sum())}, "
                  f"nas duas {int((a & b).sum())}", flush=True)
        del reference, mine
    print("CONFERÊNCIA: " + ("IGUAL À ORIGINAL (só arredondamento)" if worst < 1e-3 else "DIFERENTE"), flush=True)
    return worst < 1e-3


def run_original(torch, code, args) -> int:
    """O inference.py original, sem mudar nada nele, com a rede trocada pela versão por fatias. Confere num exame
    inteiro todo o resto do caminho (leitura, recorte, espelhamento, volumes), onde a rede original não cabe na
    memória. Os 6 canais finais da rede não entram na segmentação e vão zerados."""
    import os
    import runpy
    from pathlib import Path
    import unet3d.model as unet_model

    def slab_forward(self, x):
        with torch.no_grad():
            out = logits(torch, self, x[0, 0])
        extra = torch.zeros((self.final_conv.out_channels - N_LABELS,) + tuple(out.shape[1:]))
        return torch.cat([out, extra])[None]

    # Troca só o cálculo (forward); a classe continua a mesma, porque o __init__ original usa super(UNet3D, self).
    unet_model.UNet3D.forward = slab_forward
    os.environ.setdefault("FREESURFER_HOME", str(Path(args.modelo).resolve().parent.parent))
    sys.argv = ["inference.py", "--i", args.i, "--o", args.o, "--crop", "--threads", str(args.threads or -1)]
    if args.csv:
        sys.argv += ["--csv_vols", args.csv]
    runpy.run_path(str(Path(code) / "inference.py"), run_name="__main__")
    ok = Path(args.o).exists()
    print(f"original com a rede por fatias: {'segmentação gravada' if ok else 'falhou'}; memória máxima {peak_gb():.1f} GB",
          flush=True)
    return 0 if ok else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--codigo", required=True)
    parser.add_argument("--modelo", required=True)
    parser.add_argument("--i")
    parser.add_argument("--o")
    parser.add_argument("--csv")
    parser.add_argument("--figura")
    parser.add_argument("--json")
    parser.add_argument("--threads", type=int, default=0)
    parser.add_argument("--conferir", action="store_true")
    parser.add_argument("--original", action="store_true")
    args = parser.parse_args(argv)
    sys.path.insert(0, args.codigo)
    import torch
    import utils  # noqa: E402  (do WMH-SynthSeg)
    from unet3d.model import UNet3D  # noqa: E402

    if args.original:
        return run_original(torch, args.codigo, args)
    if args.threads > 0:
        torch.set_num_threads(args.threads)
    print(f"torch {torch.__version__}, {torch.get_num_threads()} núcleos, oneDNN "
          f"{'sim' if torch.backends.mkldnn.is_available() else 'não'}", flush=True)
    model = UNet3D(1, N_LABELS + 6, final_sigmoid=False, f_maps=64, layer_order="gcl", num_groups=8, num_levels=5,
                   is_segmentation=False, is3d=True)
    model.load_state_dict(torch.load(args.modelo, map_location="cpu")["model_state_dict"])
    model.eval()
    with torch.no_grad():
        if args.conferir:
            return 0 if check(torch, model, utils, args.i) else 1
        segment(torch, model, utils, args.i, args.o, args.csv, args.figura, args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
