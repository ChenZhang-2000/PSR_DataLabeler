import os
import time
import datetime
from collections.abc import Iterable

import numpy as np
import pandas as pd
import scipy


def _series_time_convert(times: pd.Series):
    return times.apply(_time_convert)


def _wav_full_name(sen_dir):
    def _wav_name(s: pd.Series):
        return f"{sen_dir}\\{s.iloc[0]}_{s.iloc[1]}.wav"
    return _wav_name


def _time_convert(t):
    return int(time.mktime(datetime.datetime.strptime(t, "%Y-%m-%d %H:%M:%S").timetuple()))


class Data:
    def __init__(self, sen_dirs, danmu_file):
        """
        :param sen_dir: directory of splitted sentences
        :param sen_txt_dir: file path to the transcripted senteces
        :param danmu_file: file path to the danmu file
        """
        sen_dir, sen_txt_file, _ = sen_dirs[0]
        self.sentences = Sentences(sen_dir, sen_txt_file)
        for sen_dir, sen_txt_file, t in sen_dirs[1:]:
            self.sentences.append(Sentences(sen_dir, sen_txt_file), t)

        self.sentences.data.sort_values("start", inplace=True)
        self.sentences.data.reset_index(drop=True, inplace=True)

        if isinstance(danmu_file, str):
            self.danmu = Danmu(danmu_file)
        elif isinstance(danmu_file, list) or isinstance(danmu_file, tuple):
            self.danmu = Danmu(danmu_file[0])
            t0 = self.danmu.t0
            for df in danmu_file[1:]:
                danmu = Danmu(df)
                self.danmu.append(danmu, danmu.t0-t0)
        else:
            raise

        self.danmu.data.sort_values("time", inplace=True)
        self.danmu.data.reset_index(drop=True, inplace=True)

        self.mk_timeline()

        self.history = []
        self.dialogue = scipy.sparse.lil_matrix((len(self.sentences), len(self.danmu)), dtype=np.int8)
        # streamer: the streamer of which the sender is a fan
        # fan_name: the name of fans of the streamer
        # fan_level: the level of fans
        # username: the username of the sender
        # content: the content of the danmu

    def __getitem__(self, item):
        return self.dialogue[item]

    def mk_timeline(self):

        d = []
        for t_title, data, k in [('start', self.sentences.data, 0), ('end', self.sentences.data, 0), ('time', self.danmu.data, 1)]:
            t = data.loc[:, t_title].to_numpy()
            id = data.index.to_numpy()
            s = np.ones_like(id) * k
            d.append(np.stack([id, t, s]).T)

        df = np.concatenate(d, axis=0)

        self.timeline = pd.DataFrame(df, columns=["idx", "time", "side"]).sort_values(['time', 'idx'],
                                                                                      ascending=[True, True])

    def delete(self, where, idx: int or (int, int)):
        if where == "sentence":
            self.sentences.delete(idx)
            self.history.append(("sentence", "delete"))
            self.mk_timeline()
        elif where == "danmu":
            self.danmu.delete(idx)
            self.history.append(("danmu", "delete"))
            self.mk_timeline()
        else:
            self.dialogue[idx[0], idx[1]] = 0
            self.history.append(("dialogue", ("delete", idx)))

    def modify(self, where, idx: int or (int, int), content):
        if where == "sentence":
            self.sentences.modify(idx, content)
            self.history.append(("sentence", "modify"))
        elif where == "danmu":
            self.danmu.modify(idx, content)
            self.history.append(("danmu", "modify"))
        else:
            raise

    def match(self, l_idx, r_idx):
        self.dialogue[l_idx, r_idx] = 1
        self.history.append(("dialogue", ("match", (l_idx, r_idx))))

    def undo(self):
        where, action = self.history[-1]
        if where == "sentence":
            out = self.sentences.undo()
        elif where == "danmu":
            out = self.danmu.undo()
        else:
            action, idx = action
            if action == "delete":
                self.dialogue[idx[0], idx[1]] = 1
            elif action == "match":
                self.dialogue[idx[0], idx[1]] = 0
            else:
                raise
            out = None
        self.history.pop(-1)
        self.mk_timeline()
        return out

    def data_to_save(self):
        sentence = self.sentences.data_to_save()
        danmu = self.danmu.data_to_save()
        return self.dialogue, sentence, danmu

    def save(self, filepath):
        self.sentences.save(filepath)
        self.danmu.save(filepath)
        self.dialogue


class Sentences:
    def __init__(self, sen_dir, sen_txt_file):

        self.data = pd.read_csv(sen_txt_file, header=None, names=["start", "end", "content"], index_col=0)

        self.data.insert(3, "wav_file", self.data.apply(_wav_full_name(sen_dir), axis=1), True)
        # self.shift(-self.data.iloc[0, 0])

        self.history = []

    def __len__(self):
        return self.data.index.max()+1

    def shift(self, t):
        self.data.iloc[:, 0] += t
        self.data.iloc[:, 1] += t

    def append(self, sentences, t):
        sentences.shift(t)
        self.data = pd.concat([self.data, sentences.data], ignore_index=True)
        sentences.shift(-t)

    def delete(self, idx):
        self.history.append(("delete", self.data.loc[idx]))
        self.data = self.data.drop(idx)

    def modify(self, idx, content):
        self.history.append(("modify", (idx, self.data.loc[idx, 'content'])))
        self.data.loc[idx, 'content'] = content

    def undo(self):
        action, content = self.history[-1]

        if action == "delete":
            self.data.loc[content.name] = content
            self.data = self.data.sort_index()
            out = content
        elif action == "modify":
            idx, content = content
            self.data.loc[idx, 'content'] = content
            out = (idx, content)
        else:
            raise

        self.history.pop(-1)
        return out

    def data_to_save(self):
        return self.data

    def save(self, file_path):
        self.data.to_csv(file_path, header=True, index=True)


class Danmu:
    def __init__(self, danmu_file):
        self.data = pd.read_csv(danmu_file, header=None,
                                names=["time", "streamer", "fan_name", "fan_level", "username", "content"], index_col=0)
        self.data.iloc[:, 0] = self.data.iloc[:, 0].apply(_time_convert)
        self.t0 = self.data.iloc[0, 0] * 1000
        self.shift(-self.data.iloc[0, 0])
        self.data.iloc[:, 0] *= 1000

        self.history = []

    def __len__(self):
        return self.data.index.max()+1

    def shift(self, t):
        self.data.iloc[:, 0] += t

    def append(self, danmu, t):
        danmu.shift(t)
        self.data = pd.concat([self.data, danmu.data], ignore_index=True)
        danmu.shift(-t)

    def delete(self, idx):
        self.history.append(("delete", self.data.loc[idx]))
        self.data = self.data.drop(idx)

    def modify(self, idx, content):
        self.history.append(("modify", (idx, self.data.loc[idx, 'content'])))
        self.data.loc[idx, 'content'] = content

    def undo(self):
        action, content = self.history[-1]

        if action == "delete":
            self.data.loc[content.name] = content
            self.data = self.data.sort_index()
            out = content
        elif action == "modify":
            idx, content = content
            self.data.loc[idx, 'content'] = content
            out = (idx, content)
        else:
            raise

        self.history.pop(-1)
        return out

    def data_to_save(self):
        return self.data

    def save(self, file_path):
        self.data.to_csv(file_path, header=True, index=True)


if __name__ == "__main__":
    sen_dirs = (
                   r"E:\Projects\PythonProjects\PSR-Analysis\temp\sentences\20231222-222826",
                   r"E:\Datasets\PSR\Text\whisper\20231222-222826.csv",
                   0
               ), (
                   r"E:\Projects\PythonProjects\PSR-Analysis\temp\sentences\20231222-232826",
                   r"E:\Datasets\PSR\Text\whisper\20231222-232826.csv",
                   3600000
               )
    data = Data(sen_dirs=sen_dirs,
                danmu_file=[
                    r"E:\Projects\PythonProjects\Bilibili-LiveStream-Monitor\data\20231222085001\danmu.csv",
                    # r"E:\Projects\PythonProjects\Bilibili-LiveStream-Monitor\data\20231215135832\danmu.csv",
                ])

    data.danmu.shift(-20105000)

    # data.danmu.modify(0, "222")
    # data.danmu.delete(0)
    #
    # data.danmu.undo()
    # data.danmu.undo()

    data.sentences.data.to_csv(r".\test.csv")
    data.danmu.data.to_csv(r".\test2.csv")
