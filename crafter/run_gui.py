import argparse

import numpy as np
from pathlib import Path
import joblib, copy
from datetime import datetime
try:
  import pygame
except ImportError:
  print('Please install the pygame package to use the GUI.')
  raise

import os
from PIL import Image

import crafter


def main():
  boolean = lambda x: bool(['False', 'True'].index(x))
  parser = argparse.ArgumentParser()
  parser.add_argument('--seed', type=int, default=None)
  parser.add_argument('--area', nargs=2, type=int, default=(64, 64))
  parser.add_argument('--view', type=int, nargs=2, default=(9, 9))
  parser.add_argument('--length', type=int, default=None)
  parser.add_argument('--health', type=int, default=9)
  parser.add_argument('--window', type=int, nargs=2, default=(600, 600))
  parser.add_argument('--size', type=int, nargs=2, default=(0, 0))
  parser.add_argument('--record', type=str, default=None)
  parser.add_argument('--fps', type=int, default=5)
  parser.add_argument('--wait', type=boolean, default=False)
  parser.add_argument('--death', type=str, default='reset', choices=[
      'continue', 'reset', 'quit'])
  args = parser.parse_args()

  keymap = {
      pygame.K_a: 'move_left',
      pygame.K_d: 'move_right',
      pygame.K_w: 'move_up',
      pygame.K_s: 'move_down',
      pygame.K_SPACE: 'do',
      pygame.K_TAB: 'sleep',
      pygame.K_j: 'save state to save.pkl',
      pygame.K_k: 'load state from save.pkl',
      pygame.K_i: 'toggle_recording',
      pygame.K_o: 'playback_state',

      pygame.K_r: 'place_stone',
      pygame.K_t: 'place_table',
      pygame.K_f: 'place_furnace',
      pygame.K_p: 'place_plant',

      pygame.K_1: 'make_wood_pickaxe',
      pygame.K_2: 'make_stone_pickaxe',
      pygame.K_3: 'make_iron_pickaxe',
      pygame.K_4: 'make_wood_sword',
      pygame.K_5: 'make_stone_sword',
      pygame.K_6: 'make_iron_sword',
  }
  print('Actions:')
  for key, action in keymap.items():
    print(f'  {pygame.key.name(key)}: {action}')

  crafter.constants.items['health']['max'] = args.health
  crafter.constants.items['health']['initial'] = args.health

  size = list(args.size)
  size[0] = size[0] or args.window[0]
  size[1] = size[1] or args.window[1]

  env = crafter.Env(
      area=args.area, view=args.view, length=args.length, seed=args.seed)
  env = crafter.Recorder(env, args.record)
  env.reset()
  achievements = set()
  duration = 0
  return_ = 0
  was_done = False
  print('Diamonds exist:', env._world.count('diamond'))

  pygame.init()
  screen = pygame.display.set_mode(args.window)
  clock = pygame.time.Clock()
  running = True
  recording = False
  recorded_states = []
  checkpoint_dir = Path('checkpoints')
  checkpoint_dir.mkdir(parents=True, exist_ok=True)

  while running:

    # Rendering.
    image = env.render(size)
    if size != args.window:
      image = Image.fromarray(image)
      image = image.resize(args.window, resample=Image.NEAREST)
      image = np.array(image)
    surface = pygame.surfarray.make_surface(image.transpose((1, 0, 2)))
    screen.blit(surface, (0, 0))
    pygame.display.flip()
    clock.tick(args.fps)

    # Keyboard input.
    action = None
    skip_step = False
    pygame.event.pump()
    for event in pygame.event.get():
      if event.type == pygame.QUIT:
        running = False
      elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
        running = False
      elif event.type == pygame.KEYDOWN and event.key == pygame.K_j:
        fname = 'save.pkl'
        try:
          env.save_state(fname)
          print(f'[Saved] game state to {fname}')
        except Exception as e:
          print(f'[Error] saving game state: {e}')
        skip_step = True
        continue
      elif event.type == pygame.KEYDOWN and event.key == pygame.K_k:
        fname = 'save.pkl'
        if os.path.exists(fname):
          try:
            env = crafter.Env.load_state(fname)
            print(f'[Loaded] game state {fname}')
          except Exception as e:
            print(f'[Error] loading game state: {e}')
        else:
          print(f'[Error] no save file at {fname}')
        skip_step = True
        continue
      elif event.type == pygame.KEYDOWN and event.key == pygame.K_i:
        # toggle recording
        if not recording:
          recording = True
          recorded_states = []
          print('[Recording] Started recording states.')
        else:
          recording = False
          if recorded_states:
            ts = datetime.now().strftime('%Y%m%dT%H%M%S')
            path = checkpoint_dir / f'{ts}_states.joblib'
            joblib.dump(recorded_states, path, compress=('lzma', 9))
            print(f'[Recording] Stopped. Saved {len(recorded_states)} states to {path}')
          else:
            print('[Recording] Stopped. No states recorded.')
        skip_step = True
        continue
      elif event.type == pygame.KEYDOWN and event.key == pygame.K_o:
        # playback
        try:
          idx = int(input('Enter timestep index to load: '))
        except Exception:
          print('[Playback] Invalid timestep, cancelling.')
          skip_step = True
          continue
        fname = input('Enter filename to load (Enter = latest): ').strip()
        if fname:
          path = checkpoint_dir / fname
        else:
          files = list(checkpoint_dir.glob('*.joblib'))
          if not files:
            print('[Playback] No checkpoint files.')
            skip_step = True
            continue
          path = max(files, key=lambda f: f.stat().st_mtime)
        if not path.exists():
          print(f'[Playback] File {path} not found.')
          skip_step = True
          continue
        try:
          states = joblib.load(path)
        except Exception as e:
          print(f'[Playback] Load error: {e}')
          skip_step = True
          continue
        if idx < 0 or idx >= len(states):
          print(f'[Playback] Index {idx} out of range 0–{len(states)-1}.')
          skip_step = True
          continue
        env = states[idx]
        duration = env._step
        return_ = 0
        achievements = {n for n,c in env._player.achievements.items() if c>0}
        was_done = False
        recorded_states = []
        print(f'[Playback] Loaded state {idx} from {path}.')
        skip_step = True
        continue
      elif event.type == pygame.KEYDOWN and event.key in keymap.keys():
        action = keymap[event.key]
    if action is None:
      pressed = pygame.key.get_pressed()
      for key, action in keymap.items():
        if pressed[key]:
          break
      else:
        if args.wait and not env._player.sleeping:
          continue
        else:
          action = 'noop'

    # Environment step.
    if not skip_step:
      _, reward, done, _ = env.step(env.action_names.index(action))
      duration += 1
      if recording:
        recorded_states.append(copy.deepcopy(env))
        if len(recorded_states) % 10 == 0:
            print(f'[Recording] Captured {len(recorded_states)} states.')

    # Achievements.
    unlocked = {
        name for name, count in env._player.achievements.items()
        if count > 0 and name not in achievements}
    for name in unlocked:
      achievements |= unlocked
      total = len(env._player.achievements.keys())
      print(f'Achievement ({len(achievements)}/{total}): {name}')
    if env._step > 0 and env._step % 100 == 0:
      print(f'Time step: {env._step}')
    if reward:
      print(f'Reward: {reward}')
      return_ += reward

    # Episode end.
    if done and not was_done:
      was_done = True
      print('Episode done!')
      print('Duration:', duration)
      print('Return:', return_)
      if args.death == 'quit':
        running = False
      if args.death == 'reset':
        print('\nStarting a new episode.')
        env.reset()
        achievements = set()
        was_done = False
        duration = 0
        return_ = 0
      if args.death == 'continue':
        pass

  pygame.quit()


if __name__ == '__main__':
  main()
