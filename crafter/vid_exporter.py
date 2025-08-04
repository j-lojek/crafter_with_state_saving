import argparse
import joblib
import imageio
import numpy as np
from pathlib import Path
import sys

def states_to_frames(states, size=None):
    return [s.render(size) for s in states]

def frames_to_png(frames, out_dir):
    out_dir.mkdir(exist_ok=True)
    for i, frame in enumerate(frames):
        imageio.imsave(out_dir / f'{i:06d}.png', frame)

def frames_to_mp4(frames, out_path, fps=30):
    imageio.mimsave(str(out_path), frames, fps=fps, macro_block_size=None)

def frames_to_gif(frames, out_path, fps=10):
    imageio.mimsave(str(out_path), frames, fps=fps)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', help='.joblib file with recorded states', default=None)
    p.add_argument('--format', choices=['png','mp4','gif'], default='mp4')
    p.add_argument('--output', default=None, help='output file/dir')
    p.add_argument('--fps', type=int, default=10)
    p.add_argument(
        '--size', nargs=2, type=int, default=(512, 512), metavar=('W', 'H'),
        help='resolution of img, --size 512 512'
    )
    args = p.parse_args()
    inp_path = None
    if args.input:
        inp_path = Path(args.input)
        if not inp_path.exists():
            print(f"[Error]: file {inp_path} doesn't exist.", file=sys.stderr)
            sys.exit(1)
    else:
        ckpt_dir = Path('checkpoints')
        files = list(ckpt_dir.glob('*.joblib'))
        if not files:
            print('[Error]: no .joblib files in checkpoints dir.', file=sys.stderr)
            sys.exit(1)
        inp_path = max(files, key=lambda f: f.stat().st_mtime)
        print(f'Using newest: {inp_path}')
    states = joblib.load(str(inp_path))
    size = tuple(args.size)
    frames = states_to_frames(states, size)

    if args.format == 'png':
        out = Path(args.output or inp_path.stem)
        frames_to_png(frames, out)
        print(f'Saved {len(frames)} PNGs to dir {out}.')
    else:
        out = Path(args.output or inp_path.with_suffix(f'.{args.format}'))
        if args.format == 'mp4':
            frames_to_mp4(frames, out, fps=args.fps)
        else:
            frames_to_gif(frames, out, fps=args.fps)
        print(f'Saved vid {args.format.upper()} to {out}.')

if __name__ == '__main__':
    main()
