#!/usr/bin/env python3

import nltk
import re
import logging

from typing import Optional, List, Dict, Any, Tuple

logging.basicConfig(filename='bookanalytics.log', level=logging.DEBUG)

def calc_TTR(text: str) -> float:
    """
    Calculate the Token Type Ratio for some text.
    From: https://rishavr.github.io/Hand-Coding-Our-Very-Own-Type-Token-Ratio-Generator/
    """
    # Remove all special characters
    cleaned = re.sub(r'[^\w]', ' ', text)
    cleaned = cleaned.lower()
    # Tokenize the text
    tokens = nltk.word_tokenize(cleaned)
    #print(tokens)
    types = nltk.Counter(tokens)
    #print(types)
    calculated_TTR = (len(types)/len(tokens))*100
    return calculated_TTR

def calc_FRES(text: str) -> float:
    """
    Calculate the Flesch Reading Ease Score for some text.
    From: https://www.geeksforgeeks.org/readability-index-pythonnlp/
    Implements Flesch Formula: 
    Reading Ease score = 206.835 - (1.015 × ASL) - (84.6 × ASW) 
    Here, 
        ASL = average sentence length (number of words  
            divided by number of sentences) 
        ASW = average word length in syllables (number of syllables  
            divided by number of words) 
    """
    # logging.debug("Starting calc_FRES on text with length %s", str(len(text)))
    sentences = split_sentences(text.strip())
    # Get stats
    sentence_count = len(sentences)
    # logging.debug("There are %s sentences.", str(sentence_count))
    word_count: int = 0
    syllable_count: int = 0
    for sentence in sentences:
        # Remove all special characters
        # logging.debug("Tokenizing sentence into words.")
        cleaned = re.sub(r'[^\w]', ' ', sentence)
        cleaned = cleaned.lower()
        words = nltk.word_tokenize(cleaned)
        word_count += len(sentence)
        # logging.debug("Counting syllables in sentence starting '%s'", sentence[0:20])
        syllable_count += sum(count_syllables(words))
    avg_sentence_length = float(word_count / sentence_count)
    avg_syllables_per_word = syllable_count / word_count # original code rounded this value
    # Calculate FRES
    calculated_FRES = 206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_syllables_per_word)
    return calculated_FRES

def split_sentences(text: str) -> List[str]:
    """ Splits a longer text into sentences. """
    # Initialize the sentence detector with training data
    try:
        sent_detector = nltk.data.load('tokenizers/punkt/english.pickle')
    except:
        nltk.download('punkt')
        sent_detector = nltk.data.load('tokenizers/punkt/english.pickle')

    # Tokenize into sentences
    # logging.debug("Tokenizing text into sentences")
    return sent_detector.tokenize(text.strip())

def classify_FRES(fres_score: float) -> str:
    if fres_score < 27.0:
        return "VHARD"
    elif fres_score < 63.0:
        return "HARD"
    return "OK"
    

cmu_d = None

def count_syllables(words: List[str]) -> List[int]:
    """
    Tries to get the syllable count via NLTK, if unknown word then
    fails over to a calculation with __syllables.
    Assumes the words were stripped of punctuation and lowercased.
    """
    global cmu_d
    try:
        if cmu_d is None:
            # This is slow, don't want to re-do on every call.
            cmu_d = nltk.corpus.cmudict.dict()
    except LookupError:
        logging.debug("downloading cmudict")
        nltk.download('cmudict')
        cmu_d = nltk.corpus.cmudict.dict()

    counts = []
    for word in words:
        try:
            phonemes = cmu_d[word][0]
            counts.append(len(list(y for y in phonemes if y[-1].isdigit())))
        except KeyError:
            # if word not found in cmudict
            # logging.debug("KeyError on word %s, using homebrew syllable counter.", word)
            counts.append(__syllables(word))
    return counts

def __syllables(word):
    """ Rough calculation of syllables. """
    #referred from stackoverflow.com/questions/14541303/count-the-number-of-syllables-in-a-word
    count = 0
    vowels = 'aeiouy'
    word = word.lower()
    if word[0] in vowels:
        count +=1
    for index in range(1,len(word)):
        if word[index] in vowels and word[index-1] not in vowels:
            count +=1
    if word.endswith('e'):
        count -= 1
    if word.endswith('le'):
        count += 1
    if count == 0:
        count += 1
    return count

def find_adverbs(text: str) -> List[str]:
    """ Returns all words determined to be adverbs in the text. """
    words = nltk.word_tokenize(text.lower())
    tagged = __tag_words(words)

    adverb_tags = list(filter(lambda item: item[1] == "RB", tagged))
    adverbs = list(set(map(lambda item: item[0], adverb_tags)))
    # Things that NLTK counts as adverbs, but I don't want flagged
    false_positives = [
        "n't", "not", "down", "here", "there", "always", "right", "forward",
        "as", "else", "now", "never", "also", "back", "then", "out"]
    for word in false_positives:
        if word in adverbs:
            adverbs.remove(word)
    return adverbs

def find_passive_voice(sentence: str) -> Optional[str]:
    """
    Takes a sentence, returns a substring if we think this is a passive sentence.
    Returns None if active voice.
    """
    words = nltk.word_tokenize(sentence)
    tagged = __tag_words(words)

    # Particularly, if we see a "BE" verb followed by some other, non-BE
    # verb, except for a gerund, we deem the sentence to be passive.

    found_passive = []
    for tag in tagged:
        if tag[1].startswith("VB") and verb_is_be(tag[0]):
            found_passive.append(tag[0])
        elif len(found_passive) > 0:
            # We have found a BE verb, looking for trailing VB*
            if tag[1] == "RB":
                # Ignore adverbs, can be in the middle of BE and verb
                found_passive.append(tag[0])
            elif tag[1].startswith("V") and not tag[1].startswith("VBG"):
                found_passive.append(tag[0])
                return " ".join(found_passive)
            else:
                # Reset, continue looking
                found_passive = []

    return None

def verb_is_be(verb: str) -> bool:
    return verb in ['be', 'am', 'is', 'are', 'was', 'were', 'being', 'been']

def __tag_words(words: List[str]) -> List[Tuple[str, str]]:
    try:
        return nltk.pos_tag(words)
    except LookupError:
        nltk.download('averaged_perceptron_tagger')
        return nltk.pos_tag(words)

if __name__ == '__main__':
    print("bookanalytics.py is not to be called directly.")
