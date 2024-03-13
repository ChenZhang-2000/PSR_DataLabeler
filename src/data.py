import os
import time
import datetime

import pandas as pd


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

        if danmu_file:
            self.danmu = Danmu(danmu_file)
        else:
            self.danmu = None
        # streamer: the streamer of which the sender is a fan
        # fan_name: the name of fans of the streamer
        # fan_level: the level of fans
        # username: the username of the sender
        # content: the content of the danmu


class Sentences:
    def __init__(self, sen_dir, sen_txt_file):

        self.data = pd.read_csv(sen_txt_file, header=None, names=["start", "end", "content"], index_col=0)

        self.data.insert(3, "wav_file", self.data.apply(_wav_full_name(sen_dir), axis=1), True)
        # self.shift(-self.data.iloc[0, 0])

    def shift(self, t):
        self.data.iloc[:, 0] += t
        self.data.iloc[:, 1] += t

    def append(self, sentences, t):
        sentences.shift(t)
        self.data = pd.concat([self.data, sentences.data], ignore_index=True)
        sentences.shift(-t)


class Danmu:
    def __init__(self, danmu_file):
        self.data = pd.read_csv(danmu_file, header=None,
                                names=["time", "streamer", "fan_name", "fan_level", "username", "content"], index_col=0)
        self.data.iloc[:, 0] = self.data.iloc[:, 0].apply(_time_convert)
        self.shift(-self.data.iloc[0, 0])
        self.data.iloc[:, 0] *= 1000

        self.history = []

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
        elif action == "modify":
            idx, content = content
            self.data.loc[idx, 'content'] = content
        else:
            raise

        self.history.pop(-1)


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
                danmu_file=r"E:\Projects\PythonProjects\Bilibili-LiveStream-Monitor\data\20231222085001\danmu.csv")


    data.danmu.modify(0, "222")
    data.danmu.delete(0)

    data.danmu.undo()
    data.danmu.undo()

    data.sentences.data.to_csv(r".\test.csv")
    data.danmu.data.to_csv(r".\test2.csv")
