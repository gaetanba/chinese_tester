from collections import defaultdict
import random
import csv
import requests
import string
import unicodedata
import math
import time


def sigmoide(elements, lamb=1, increasing=True):
    items = []
    l = len(elements)
    x0 = -l // 2
    xn = abs(x0) - l % 2
    i = lambda i: 1 - i * 2

    for x in range(x0, xn):
        r = l / (1 + math.e ** (i(increasing) * x * lamb))
        items.append(r)

    return items


def format_dictionary_todict(dictionary):
    dic = []
    for element in dictionary:
        word, pronunciation, translation = element
        dic.append(
            dict(
                word=word.split(" / "),
                pronunciation=pronunciation.split(" / "),
                translation=translation.split(" / "),
            )
        )
    return dic


def get_dictionary(spreadsheetURL=None):
    if spreadsheetURL is None:
        spreadsheetURL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSu9lE7IWNrwypkuhQ2MmtGmfImmVVHW57GG4dE8ij5lP06SRhPPIHq5G5w_8NdIgN9-voL4kEMwzYS/pub?gid=520398043&single=true&output=csv"

    response = requests.get(spreadsheetURL)
    data = response.content
    dictionary = list(csv.reader(data.decode("utf-8").splitlines()))

    return format_dictionary_todict(dictionary)


def convert_to_int(e):
    if isinstance(e, (int, float)):
        return int(e)
    elif isinstance(e, str):
        try:
            return int(e)
        except:
            return None
    return None


def pop_accent(character):
    composition = unicodedata.decomposition(character).split()
    for comp in composition:
        char = chr(int(comp, 16))
        if char in string.ascii_letters:
            return char
    return character


def sanitize_string(string, removeAccent=True):
    elements_to_remove = [" ", "\n", "\t"]
    for elem in elements_to_remove:
        string = string.replace(elem, "")
    string = string.lower()
    if removeAccent:
        ns = ""
        for char in string:
            ns += pop_accent(char)
        return ns
    return string


def sanitize_element(element):
    if isinstance(element, list):
        return [sanitize_string(e) for e in element]
    elif isinstance(element, str):
        return sanitize_string(element)
    else:
        return element


def convert_list_to_string(iterable):
    text = ""
    if isinstance(iterable, str):
        return iterable
    for elem in iterable:
        if isinstance(elem, str):
            text += f"{elem} "
        else:
            text += convert_list_to_string(elem)
    return text


class Settings:
    _available_distribution = (
            "sigmoide_i",
            "sigmoide_-i",
            "uniform",
            "linear_i",
            "linear_-i", 
            "gaussian"
        )

    def __init__(self, controller):
        self.sound = False
        self.test_range = []
        self.controller = controller
        self.distribution = "sigmoide_i"
        
    @property
    def available_range(self):
        return f"0, {len(controller._dictionary)}"

    def __repr__(self):
        text = f"""
    1- sound = {self.sound}

    2- test_range = {', '.join([str(x) for x in self.test_range])} (-> {self.available_range})

    3- distribution = {self.distribution}, 
        (
            1- sigmoide_i    ???/???
            2- sigmoide_-i   ???\\???
            3- uniform       ????????????
            4- linear_i      /
            5- linear_-i     \\
            6- gaussian      ???/\\???
        )
    """
        return text

    def set(self, value):
        value = value.replace(" = ", "=")
        k, v = value.split("=")

        if k in ["sound", "1"]:
            try:
                self.sound = int(v)
            except:
                return False

        elif k in ["test_range", "2"]:
            try:
                v = v.replace(" ", "")
                v0, vn = v.split(",")
                self.test_range = [int(v0), int(vn)]
            except:
                return False

        elif k in ["distribution", "3"]:
            i = convert_to_int(v)
            if i is not None and i <= len(self._available_distribution):
                self.distribution = self._available_distribution[i - 1]
            elif v in self._available_distribution:
                self.distribution = v
            else:
                return False

        else:
            return False

        return True


class Controller:
    def __init__(self):
        self.retention = 10
        self.recently_seen = []
        self._dictionary = []
        self.settings = Settings(self)

    @property
    def dictionary(self):
        v0, vn = self.settings.test_range
        return self._dictionary[v0:vn]

    @dictionary.setter
    def dictionary(self, value):
        self._dictionary = value
        self.settings.test_range = [0, len(value)]

    def instanciate_data(self):
        # self.dictionary = dictionary
        self.word_2_pronunciation = {}
        self.pronunciation_2_word = defaultdict(list)
        self.translation_2_word = defaultdict(list)
        self.word_2_translation = defaultdict(list)

        self.word_2_pronunciation_sanitized = {}
        self.pronunciation_2_word_sanitized = defaultdict(list)
        self.translation_2_word_sanitized = defaultdict(list)
        self.word_2_translation_sanitized = defaultdict(list)

        self.all_chars = set()
        for elem in self.dictionary:
            pronunciation = elem.get("pronunciation")
            translation = elem.get("translation")
            word = elem.get("word")
            for w in word:
                for x in w:
                    self.all_chars.add(x)
            for i, c in enumerate(word):
                self.word_2_pronunciation[c] = pronunciation[i]
                self.word_2_translation[c].extend(translation)
                self.word_2_pronunciation_sanitized[
                    sanitize_element(c)
                ] = sanitize_element(pronunciation[i])
                self.word_2_translation_sanitized[sanitize_element(c)].extend(
                    sanitize_element(translation)
                )
            for t in translation:
                self.translation_2_word[t].extend(word)
                self.translation_2_word_sanitized[sanitize_element(t)].extend(
                    sanitize_element(word)
                )
        for k, v in self.word_2_pronunciation.items():
            self.pronunciation_2_word[v].append(k)
            self.pronunciation_2_word_sanitized[sanitize_element(v)].append(
                sanitize_element(k)
            )

    def _reformatstring(self, e):
        return [e, e.replace(" ", ""), e.lower()]

    def _add_item(self, index):
        if len(self.recently_seen) >= self.retention:
            self.recently_seen.pop(0)
        self.recently_seen.append(index)

    def _select_item(self, dictionary=None):
        if dictionary is None:
            dictionary = self.dictionary
        lenght = len(dictionary)
        if self.settings.distribution == "sigmoide_i":
            weights = sigmoide(dictionary, lamb=10 / lenght)
        elif self.settings.distribution == "sigmoide_-i":
            weights = sigmoide(dictionary, lamb=10 / lenght, increasing = False)
        elif self.settings.distribution == "uniform":
            weights = [1]*len(dictionary)
        elif self.settings.distribution == "linear_i":
            weights = range(len(dictionary))
        elif self.settings.distribution == "linear_-i":
            weights = range(len(dictionary), 0)
        selected_list = random.choices(dictionary, weights=weights, k=1)
        selected_item = selected_list[0]
        index = dictionary.index(selected_item)
        return index, selected_item

    def dictation(self, number=10):
        items = []
        added = []
        v0, vn = self.settings.test_range
        available_items = [
            x for x in list(self.word_2_translation.keys())[v0:vn] if len(x) > 1
        ]
        if number >= len(available_items):
            number = len(available_items)
            random.shuffle(available_items)
            items = available_items
            return items
        else:
            for i in range(number):
                index, selected_item = self._select_item(dictionary=available_items)
                while index in added:
                    index, selected_item = self._select_item(dictionary=available_items)
                added.append(index)
                items.append(selected_item)
        return items

    def select_question(self, mode="random"):
        index, selected_item = self._select_item()
        while index in self.recently_seen:
            index, selected_item = self._select_item()

        if mode == "random":
            self.selected_category = random.choice(list(selected_item.keys()))
        else:
            self.selected_category = mode

        self.selected_question = random.choice(selected_item[self.selected_category])

        if self.selected_category == "word":
            word = self.selected_question
            translation = self.word_2_translation[self.selected_question]
        elif self.selected_category == "pronunciation":
            word = self.pronunciation_2_word[self.selected_question]
            translation = [self.word_2_translation[w] for w in word]
        else:  # category == "translation"
            translation = self.selected_question
            word = self.translation_2_word.get(translation)
        self.answer = dict(word=word, translation=translation)
        self._add_item(index)

    def verify_answer(self, word="", pronunciation="", translation=""):
        if self.selected_category == "pronunciation":
            anwserwords = sanitize_element(self.answer["word"])
            if not word in self.answer["word"]:
                return False
            answertranslation = sanitize_element(
                self.answer["translation"][self.answer["word"].index(word)]
            )
            if word in anwserwords and translation in answertranslation:
                return True

        elif self.selected_category == "word":
            for p in self._reformatstring(pronunciation):
                answerpronunciation = sanitize_element(
                    self.word_2_pronunciation_sanitized.get(word, "")
                )
                answertranslation = sanitize_element(
                    self.word_2_translation_sanitized.get(word, "")
                )
                if p == answerpronunciation and translation in answertranslation:
                    return True

        else:
            for p in self._reformatstring(pronunciation):
                answerword = sanitize_element(
                    self.translation_2_word_sanitized.get(translation, "")
                )
                answerpronunciation = sanitize_element(
                    self.word_2_pronunciation_sanitized.get(word, "")
                )
                if word in answerword and p == answerpronunciation:
                    return True
        return False

    def input_answer(self, text, controller):
        value = input(text)
        # help
        if value == "help" and controller.selected_category != "word":
            print("".join(sorted(list(self.all_chars))))
            value = self.input_answer(text, controller)
            return value
        elif value in ["help", "sound", "s"] and controller.selected_category == "word":
            self.speech_word(controller.selected_question)
            value = self.input_answer(text, controller)
            return value
        elif value in ["help", "sound", "s"]:
            print("".join(sorted(list(self.all_chars))))
            value = self.input_answer(text, controller)
            self.speech_word(controller.selected_question)
            value = self.input_answer(text, controller)
            return value
        if value in ["settings"]:
            print(self.settings, "\n")
            settings(self)
            print(f"({self.selected_question})")
            value = self.input_answer(text, controller)
            return value
        return value

    def speech_word(self, word, lang="zh-CN"):
        import speech

        speech.say(word, language=lang)
        speech.wait()


def contest(controller, round=20, mode="random"):
    print("\n")
    count = 0
    for i in range(round):

        controller.select_question(mode)

        print(
            f"{str(i+1).zfill(len(str(round)))}/{round}: {controller.selected_category} is:",
            controller.selected_question,
        )

        if controller.selected_category == "pronunciation":
            pronunciation = controller.selected_question
            word = controller.input_answer("\t??? word: ", controller)
            if controller.settings.sound:
                controller.speech_word(word)
            translation = controller.input_answer("\t??? translation: ", controller)
        elif controller.selected_category == "word":
            word = controller.selected_question
            if controller.settings.sound:
                controller.speech_word(word)
            pronunciation = controller.input_answer("\t??? pronunciation: ", controller)
            translation = controller.input_answer("\t??? translation: ", controller)
        else:
            translation = controller.selected_question
            word = controller.input_answer("\t??? word: ", controller)
            if controller.settings.sound:
                controller.speech_word(word)
            pronunciation = controller.input_answer("\t??? pronunciation: ", controller)

        result = controller.verify_answer(
            word=sanitize_element(word),
            pronunciation=sanitize_element(pronunciation),
            translation=sanitize_element(translation),
        )

        if not result:
            answer = dict(controller.answer)
            if isinstance(answer["word"], list):
                word = answer["word"][0]
            else:
                word = answer["word"]
            answer["pronunciation"] = controller.word_2_pronunciation[word]
            answer_string = ""
            for k, v in answer.items():
                v = convert_list_to_string(v)
                answer_string += f"{k}: {v}, "
            print("????????????", result, "answer:", answer_string, "\n")
        else:
            print("????????????", result, "\n")
            count += 1

    score = f"{str(count).zfill(len(str(round)))}/{round}"
    print(f"End, score={score}\n")
    restart = input("New round? y / n:\n")
    if restart == "y":
        contest(controller, round, mode)


def dictation(controller, round):
    print("\n")

    def inputdictation(controller, verified=False):
        def print_answer(controller):
            print("word:", sentence)
            print(
                "pronunciation:",
                convert_list_to_string(controller.word_2_pronunciation[sentence]),
            )
            print(
                "translation:",
                convert_list_to_string(controller.word_2_translation[sentence]),
            )

        controller.speech_word(sentence)
        inp = input("repeat / verify / next: ")
        repeat_choices = ["r", "repeat", "R", "Repeat"]
        if inp in repeat_choices:
            inputdictation(controller, verified)
        elif inp in ["verify", "Verify", "v", "V"]:
            print_answer(controller)
            verified = True
            inp = input("repeat / next: ")
            if inp in repeat_choices:
                inputdictation(controller, verified)
        elif inp in ["settings"]:
            print(controller.settings, "\n")
            settings(controller)
            inputdictation(controller, verified)
        else:
            if not verified:
                print_answer(controller)
                time.sleep(2)

    sentences = controller.dictation(round)

    for sentence in sentences:
        inputdictation(controller)
        print("\n")

    restart = input("New round? y / n:\n")
    if restart == "y":
        dictation(controller, round)


def speach(controller, prev=""):
    to_say = input("word(s): ")
    if to_say in ["stop", "s", "return"]:
        return
    if to_say in ["r", "repeat"]:
        controller.speech_word(prev)
        speach(controller, prev)
    else:
        controller.speech_word(to_say)
        speach(controller, to_say)


def settings(controller):

    value = input("name = value -> ")

    if value in ["r", "return"]:
        return

    else:
        response = controller.settings.set(value)
        if response:
            print("\n")
            print(controller.settings)
            print("\n")
        else:
            print("Wrong value")
    settings(controller)


def menu(controller):
    question_listening = input("Questions / dictation / speach / settings: ")

    print("\n")
    if question_listening in [
        "Questions",
        "questions",
        "question",
        "Question",
        1,
        "1",
        "q",
        "Q",
    ]:

        number_of_round = convert_to_int(input("How many questions? "))
        assert number_of_round
        print(
            "\nmode:\n    1-random\n    2-word\n    3-pronunciation\n    4-translation"
        )
        m = convert_to_int(input("give index: "))
        print("\n")
        assert m in [1, 2, 3, 4]
        mode = ["random", "word", "pronunciation", "translation"][m - 1]

        # start_settings = input("start or settings: ")
        # assert start_settings in ["start", "settings", "1", 1]
        # if start_settings in ["start", "1", 1]:
        print("\n--------------------------")
        print("        Here we go")
        print("--------------------------")

        contest(controller, round=int(number_of_round), mode=mode)
        print("\n")
        menu(controller)

    elif question_listening in ["Dictation", "dictation", 2, "2", "d", "D"]:
        number_of_round = convert_to_int(input("How many sentences? "))
        assert number_of_round
        print("\n--------------------------")
        print("        Here we go")
        print("--------------------------")

        dictation(controller, number_of_round)
        print("\n")
        menu(controller)

    elif question_listening in ["Speach", "speach", 3, "3", "s", "S"]:
        # number_of_round = convert_to_int(input("How many sentences? "))
        # assert number_of_round
        print("\n--------------------------")
        print("        Here we go")
        print("--------------------------")

        speach(controller)
        print("\n")
        menu(controller)

    elif question_listening in ["Settings", "settings", 4, "4", "se", "Se"]:
        # number_of_round = convert_to_int(input("How many sentences? "))
        # assert number_of_round
        print("\n--------------------------")
        print("        Settings")
        print("--------------------------")
        print("\n")
        print(controller.settings)
        print("\n")
        settings(controller)
        print("\n")
        menu(controller)

    else:
        # todo implement settings
        menu(controller)
        pass


if __name__ == "__main__":
    controller = Controller()
    dictionary = get_dictionary()
    controller.dictionary = dictionary
    controller.instanciate_data()
    menu(controller)
