
import os
import struct
import wave
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText


STEP_TABLE = [
    7, 8, 9, 10, 11, 12, 13, 14, 16, 17,
    19, 21, 23, 25, 28, 31, 34, 37, 41, 45,
    50, 55, 60, 66, 73, 80, 88, 97, 107, 118,
    130, 143, 157, 173, 190, 209, 230, 253, 279, 307,
    337, 371, 408, 449, 494, 544, 598, 658, 724, 796,
    876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066,
    2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358,
    5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899,
    15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767
]

INDEX_TABLE = [
    -1, -1, -1, -1, 2, 4, 6, 8,
    -1, -1, -1, -1, 2, 4, 6, 8
]


class IMAState:
    def __init__(self, predictor=0, index=0):
        self.predictor = int(predictor)
        self.index = int(index)

        if self.index < 0: self.index = 0
        if self.index > len(STEP_TABLE)-1: self.index = len(STEP_TABLE)-1

    def decode_nibble(self, nibble):

        step = STEP_TABLE[self.index]
        diff = step >> 3
        if nibble & 4:
            diff += step
        if nibble & 2:
            diff += step >> 1
        if nibble & 1:
            diff += step >> 2
        if nibble & 8:
            diff = -diff

        self.predictor += diff

        if self.predictor > 32767:
            self.predictor = 32767
        elif self.predictor < -32768:
            self.predictor = -32768

        self.index += INDEX_TABLE[nibble]
        if self.index < 0:
            self.index = 0
        elif self.index > len(STEP_TABLE)-1:
            self.index = len(STEP_TABLE)-1

        return int(self.predictor)



def decode_ima_nibble_interleaved_stereo(raw_bytes, init_predictor=(0,0), init_index=(0,0), nibble_order='lo_hi'):
    state_l = IMAState(init_predictor[0], init_index[0])
    state_r = IMAState(init_predictor[1], init_index[1])

    left = []
    right = []

    for b in raw_bytes:
        lo = b & 0x0F
        hi = (b >> 4) & 0x0F
        if nibble_order == 'lo_hi':
            left.append(state_l.decode_nibble(lo))
            right.append(state_r.decode_nibble(hi))
        else:
            right.append(state_r.decode_nibble(lo))
            left.append(state_l.decode_nibble(hi))

    return left, right


def decode_ima_block_split_stereo(raw_bytes, init_predictor=(0,0), init_index=(0,0), block_size=256, nibble_order='lo_hi'):
    if block_size <= 0:
        raise ValueError('block_size must be > 0')

    left = []
    right = []
    pos = 0
    data_len = len(raw_bytes)

    while pos < data_len:
        block = raw_bytes[pos:pos+block_size]
        if len(block) == 0:
            break
        half = len(block) // 2
        ch0 = block[:half]
        ch1 = block[half:]
        l, r = decode_ima_nibble_interleaved_stereo(ch0, init_predictor, init_index, nibble_order)
        l2, r2 = decode_ima_nibble_interleaved_stereo(ch1, init_predictor, init_index, nibble_order)
        pos += block_size
    return decode_ima_block_channel_split_mono(raw_bytes, init_predictor, init_index, block_size, nibble_order)


def decode_ima_block_channel_split_mono(raw_bytes, init_predictor=(0,0), init_index=(0,0), block_size=256, nibble_order='lo_hi'):
    Returns (left_samples, right_samples)
    left = []
    right = []
    pos = 0
    data_len = len(raw_bytes)

    while pos < data_len:
        block = raw_bytes[pos:pos+block_size]
        pos += block_size
        if len(block) == 0:
            break
        half = len(block) // 2
        ch0 = block[:half]
        ch1 = block[half:]

        s0 = IMAState(init_predictor[0], init_index[0])
        s1 = IMAState(init_predictor[1], init_index[1])
        for b in ch0:
            lo = b & 0x0F
            hi = (b >> 4) & 0x0F
            if nibble_order == 'lo_hi':
                left.append(s0.decode_nibble(lo))
                left.append(s0.decode_nibble(hi))
            else:
                left.append(s0.decode_nibble(hi))
                left.append(s0.decode_nibble(lo))
        for b in ch1:
            lo = b & 0x0F
            hi = (b >> 4) & 0x0F
            if nibble_order == 'lo_hi':
                right.append(s1.decode_nibble(lo))
                right.append(s1.decode_nibble(hi))
            else:
                right.append(s1.decode_nibble(hi))
                right.append(s1.decode_nibble(lo))

    return left, right


def interleave_and_write_wav(out_path, left_samples, right_samples, sample_rate=44100):

    n = max(len(left_samples), len(right_samples))
    left = left_samples + [0] * (n - len(left_samples))
    right = right_samples + [0] * (n - len(right_samples))

    with wave.open(out_path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(int(sample_rate))
        frames = bytearray()
        for i in range(n):
            frames += struct.pack('<h', left[i])
            frames += struct.pack('<h', right[i])
        w.writeframes(frames)



class XARipperApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Behavior Interactive/Artificial Mind & Movement (PC) .xa IMA ADPCM Ripper')
        self.geometry('820x520')


        frame_files = ttk.LabelFrame(self, text='Files')
        frame_files.pack(fill='x', padx=8, pady=6)

        btn_frame = ttk.Frame(frame_files)
        btn_frame.pack(side='right', padx=6, pady=6)
        ttk.Button(btn_frame, text='Add Files', command=self.add_files).pack(side='top', fill='x')
        ttk.Button(btn_frame, text='Remove Selected', command=self.remove_selected).pack(side='top', fill='x', pady=4)
        ttk.Button(btn_frame, text='Clear', command=self.clear_files).pack(side='top', fill='x')

        self.list_files = tk.Listbox(frame_files, height=6)
        self.list_files.pack(side='left', fill='both', expand=True, padx=6, pady=6)


        options = ttk.LabelFrame(self, text='Decoding Options')
        options.pack(fill='x', padx=8, pady=6)

        opts = ttk.Frame(options)
        opts.pack(fill='x', padx=6, pady=6)

        ttk.Label(opts, text='Sample rate:').grid(row=0, column=0, sticky='w')
        self.entry_rate = ttk.Entry(opts, width=8)
        self.entry_rate.insert(0, '44100')
        self.entry_rate.grid(row=0, column=1, sticky='w')

        ttk.Label(opts, text='Initial predictor L:').grid(row=0, column=2, sticky='w')
        self.entry_pred_l = ttk.Entry(opts, width=6)
        self.entry_pred_l.insert(0, '0')
        self.entry_pred_l.grid(row=0, column=3, sticky='w')

        ttk.Label(opts, text='Initial index L:').grid(row=0, column=4, sticky='w')
        self.entry_index_l = ttk.Entry(opts, width=6)
        self.entry_index_l.insert(0, '0')
        self.entry_index_l.grid(row=0, column=5, sticky='w')

        ttk.Label(opts, text='Initial predictor R:').grid(row=1, column=2, sticky='w')
        self.entry_pred_r = ttk.Entry(opts, width=6)
        self.entry_pred_r.insert(0, '0')
        self.entry_pred_r.grid(row=1, column=3, sticky='w')

        ttk.Label(opts, text='Initial index R:').grid(row=1, column=4, sticky='w')
        self.entry_index_r = ttk.Entry(opts, width=6)
        self.entry_index_r.insert(0, '0')
        self.entry_index_r.grid(row=1, column=5, sticky='w')

        ttk.Label(opts, text='Interleave mode:').grid(row=2, column=0, sticky='w')
        self.mode_var = tk.StringVar(value='nibble')
        ttk.OptionMenu(opts, self.mode_var, 'nibble', 'nibble', 'block-split').grid(row=2, column=1, sticky='w')

        ttk.Label(opts, text='Nibble order:').grid(row=2, column=2, sticky='w')
        self.nibble_var = tk.StringVar(value='lo_hi')
        ttk.OptionMenu(opts, self.nibble_var, 'lo_hi', 'lo_hi', 'hi_lo').grid(row=2, column=3, sticky='w')

        ttk.Label(opts, text='Block size (bytes):').grid(row=2, column=4, sticky='w')
        self.entry_block = ttk.Entry(opts, width=8)
        self.entry_block.insert(0, '256')
        self.entry_block.grid(row=2, column=5, sticky='w')


        action_frame = ttk.Frame(self)
        action_frame.pack(fill='x', padx=8, pady=6)

        ttk.Button(action_frame, text='Decode Selected', command=self.decode_selected).pack(side='left')
        ttk.Button(action_frame, text='Decode All', command=self.decode_all).pack(side='left', padx=6)
        ttk.Button(action_frame, text='Exit', command=self.quit).pack(side='right')


        log_frame = ttk.LabelFrame(self, text='Log')
        log_frame.pack(fill='both', expand=True, padx=8, pady=6)
        self.log = ScrolledText(log_frame, height=10)
        self.log.pack(fill='both', expand=True)


        self.files = []

    def log_write(self, *parts):
        self.log.insert('end', ' '.join(str(p) for p in parts) + '\n')
        self.log.see('end')

    def add_files(self):
        paths = filedialog.askopenfilenames(filetypes=[('XA files', '*.xa'), ('All files', '*.*')])
        for p in paths:
            if p not in self.files:
                self.files.append(p)
                self.list_files.insert('end', p)
                self.log_write('Added:', p)

    def remove_selected(self):
        sel = list(self.list_files.curselection())
        for i in reversed(sel):
            val = self.list_files.get(i)
            self.files.remove(val)
            self.list_files.delete(i)
            self.log_write('Removed:', val)

    def clear_files(self):
        self.files.clear()
        self.list_files.delete(0, 'end')
        self.log_write('Cleared files')

    def decode_all(self):
        if not self.files:
            messagebox.showinfo('No files', 'No files to decode')
            return
        for f in list(self.files):
            self.decode_file(f)

    def decode_selected(self):
        sel = self.list_files.curselection()
        if not sel:
            messagebox.showinfo('No selection', 'Select files in the list first')
            return
        for i in sel:
            f = self.list_files.get(i)
            self.decode_file(f)

    def decode_file(self, path):
        try:
            self.log_write('Decoding:', path)
            with open(path, 'rb') as fh:
                data = fh.read()

            sample_rate = int(self.entry_rate.get())
            pred_l = int(self.entry_pred_l.get())
            pred_r = int(self.entry_pred_r.get())
            idx_l = int(self.entry_index_l.get())
            idx_r = int(self.entry_index_r.get())
            nibble_order = self.nibble_var.get()
            mode = self.mode_var.get()
            block_size = int(self.entry_block.get())

            if mode == 'nibble':
                left, right = decode_ima_nibble_interleaved_stereo(data, (pred_l, pred_r), (idx_l, idx_r), nibble_order)
            else:
                left, right = decode_ima_block_channel_split_mono(data, (pred_l, pred_r), (idx_l, idx_r), block_size, nibble_order)

            out_path = os.path.splitext(path)[0] + '.wav'
            interleave_and_write_wav(out_path, left, right, sample_rate)
            self.log_write('Wrote:', out_path, f'(samples L={len(left)} R={len(right)})')
        except Exception as e:
            self.log_write('Error decoding', path, ':', e)
            messagebox.showerror('Error', f'Error decoding {path}: {e}')


if __name__ == '__main__':
    app = XARipperApp()
    app.mainloop()
