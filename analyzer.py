import getopt
import json
import sys
import os

import matplotlib.pyplot as plt
import numpy as np
from moviepy import *
from moviepy.editor import *
from moviepy.video.io.bindings import mplfig_to_npimage
from scipy.io.wavfile import read, write

from eq import create_filter, process_signal


def help():
    print(
        'Usage: python analyzer.py -p {profile_path} -i {input_file_path} -o {output_file_path} [optional parameters]'
    )
    print('\tParameters:')
    print(
        '\t\t-p [--profile=]: sets the path for the profile file. The file must be a `.json` in the format generated by equapyzer'
    )
    print('\t\t-i [--iput=]: path to the input `.wav`')
    print('\t\t-o [--output=]: path to the output')
    print('\tOptional parameters:')
    print('\t\t-h [--help]: displays this message')
    print(
        '\t\t-f [--frequency] update frequency of the created animation (fps) [default=10]'
    )
    print(
        '\t\t-b [--buffer] buffer size, size of the FFT window in samples (default=512)'
    )
    print(
        '\t\t-a [--audio] creates video with audio. This cannot be used with -b neither -f'
    )
    sys.exit()


def psd_y(signal):
    fft = np.abs(np.fft.fft(signal))
    fft = fft[:len(fft) // 2]
    reference = 2 ** 16
    response = 20*np.log10(fft / reference)
    return response


def psd_x(signal):
    fft = np.abs(np.fft.fft(signal))
    x = np.fft.fftfreq(len(fft), d=1 / Fs)[: len(fft) // 2]
    return x


def make_frame(t):
    frame = int(t * frequency)   # Convert time to frame number

    # Axis (0, 0): input time plot
    axs[0, 0].clear()
    axs[0, 0].plot(x_frames[frame], input_frames[frame])
    axs[0, 0].set_xlim(x_frames[frame].min(), x_frames[frame].max())
    axs[0, 0].set_ylim(
        1.5 * input_frames[frame].min(), 1.5 * input_frames[frame].max()
    )

    # Axis (1, 0): output time plot
    axs[1, 0].clear()
    axs[1, 0].plot(x_frames[frame], output_frames[frame])
    axs[1, 0].set_xlim(x_frames[frame].min(), x_frames[frame].max())
    axs[1, 0].set_ylim(
        1.5 * input_frames[frame].min(), 1.5 * input_frames[frame].max()
    )

    # Axis (0, 1): input frequency plot
    axs[0, 1].clear()
    axs[0, 1].plot(
        input_frequency_x_frames[frame], input_frequency_y_frames[frame]
    )
    axs[0, 1].set_ylim(-100, 2)
    axs[0, 1].set_xlim(0, 20000)

    # Axis (1, 1): output frequency plot
    axs[1, 1].clear()
    axs[1, 1].plot(
        output_frequency_x_frames[frame], output_frequency_y_frames[frame]
    )
    axs[1, 1].set_ylim(-100, 2)
    axs[1, 1].set_xlim(0, 20000)

    return mplfig_to_npimage(fig)


plt.ion()
np.seterr(all='ignore')


# Get cli arguments
argv = sys.argv[1:]
try:
    opts, args = getopt.gnu_getopt(
        argv,
        'p:i:o:h:f:a:b:',
        [
            'profile=',
            'input=',
            'output=',
            'help',
            'frequency=',
            'display=',
            'buffer=',
            'audio=',
        ],
    )
except:
    help()

profile_path, input_path, output_path = None, None, None
frequency, display = 10, 10
buff_size = 512
a_set, b_set, f_set = False, False, False
for opt, value in opts:
    if opt in ['-h', '--helpt']:
        help()
    elif opt in ['-p', '--profile']:
        profile_path = value
    elif opt in ['-i', '--input']:
        input_path = value
    elif opt in ['-o', '--output']:
        output_path = value
    elif opt in ['-f', '--frequency']:
        try:
            frequency = int(value)
            f_set = True
        except ValueError:
            print('Frequency value must be an integer!')
            help()
    elif opt in ['-b', '--buffer']:
        try:
            buff_size = int(value)
            b_set = True
        except ValueError:
            print('Buffer size must be an integer!')
            help()
    elif opt in ['-a', '--audio']:
        try:
            assert value in ['in', 'out']
            audio = value
            frequency = 30
            a_set = True
        except AssertionError:
            print('Audio must be one of `in` or `out`')
if a_set and (b_set or f_set):
    print('When audio is set neither buffer size nor frequency can be passed')
    help()

if profile_path is None or input_path is None or output_path is None:
    help()


# Get .wav data
Fs, s = read(input_path)
try:
    if s.shape[1] != 1:
        s = s[:, 0]
except IndexError:
    ...

# Sound info
n_samples = len(s)
total_duration = n_samples / Fs
n_frames = int(n_samples * frequency / (Fs))
frame_duration = total_duration / n_frames

# Calculate buff_size if needed
if a_set:
    buff_size = int(n_samples / n_frames)


# Get equalizer data
with open(profile_path, 'r') as f:
    gains = json.loads(f.read())
freqs, gains = list(map(int, gains.keys())), list(gains.values())
freqs.insert(0, 0)
freqs.append(Fs / 2)
gains.insert(0, 0)
gains.append(-100)
filter = create_filter(freqs, gains, Fs, 2**16 - 1)


# Configure animation plots
fig, axs = plt.subplots(nrows=2, ncols=2, figsize=(16, 10))


# Get plotting frames
x_frames = [
    np.linspace(
        frame * frame_duration, (frame + 1) * frame_duration, buff_size
    )
    for frame in range(n_frames)
]
input_frames = [
    s[frame * buff_size : (frame + 1) * buff_size] for frame in range(n_frames)
]
output_frames = list(
    map(lambda window: process_signal(window, filter, gain=1), input_frames)
)

# PSD frames
input_frequency_x_frames = list(map(psd_x, input_frames))
input_frequency_y_frames = list(map(psd_y, input_frames))
output_frequency_x_frames = list(map(psd_x, output_frames))
output_frequency_y_frames = list(map(psd_y, output_frames))


# Create and save animation
animation = VideoClip(make_frame, duration=total_duration)
if a_set:
    if audio == 'in':
        animation.audio = AudioFileClip(input_path)
    elif audio == 'out':
        full_audio = np.append(output_frames[0], output_frames[1:])
        write('tmp.wav', Fs, full_audio)
        animation.audio = AudioFileClip('tmp.wav')
animation.write_videofile(output_path, fps=frequency)

if os.path.exists('tmp.wav'):
    os.remove('tmp.wav')
