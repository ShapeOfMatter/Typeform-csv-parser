#!/usr/bin/env python3

import csv
import datetime
import itertools
from typing import Dict, Iterable, List, Optional, Union

def parse( survey: Iterable[SurveyQuestion] , results: Iterable[List[str]] ) -> SurveyResponses:
    results_iter = iter(results)
    retval = SurveyResponses(survey, next(results_iter))
    for r in results_iter:
        retval.ingest(*r)
    return retval

class SurveyQuestion (object):
    def __init__(self):
        raise NotImplementedError( "SurveyQuestion abstract; it can not be instantiated." )

    def get_question_text(self) -> str:
        return self.question_text

    def get_short_name(self) -> str:
        return self.short_name

    def get_length(self) -> int:
        return self.length

    def clean(self, *response: str):
        return ''.join(response)

    def validate_heading(self, *head: str) -> bool:
        return head and head[0] and self.get_question_text() == head[0]

class _BaseQuestion (SurveyQuestion):
    def __init__(self, question_text: str, short_name: str = None):
        self.question_text = question_text
        self.short_name = short_name or question_text
        self.length = 1

class TextQuestion (_BaseQuestion):
    pass

class MetaData (TextQuestion):
    response_id = MetaData('#', 'ID')
    network_id = MetaData('Network ID')

class DateTimeQuestion (_BaseQuestion):
    start = DateTimeQuestion('Start Date (UTC)', 'Start Date')
    end = DateTimeQuestion('Submit Date (UTC)', 'End Date')

    def clean(self, *response: str) -> Optional[datetime.datetime]:
        return datetime.strptime(response[0], '%Y-%m-%d %H:%M:%S') if response and response[0] else None
    
class IntegerQuestion (_BaseQuestion):
    def clean(self, *response: str) -> Optional[int]:
        return int(response[0]) if response and response[0] else None

class BoolQuestion (IntegerQuestion):
    def clean(self, *response: str) -> Optional[bool]:
        num = super().clean(*response)
        return None if num is None else bool(num)

class ChoiceQuestion (_BaseQuestion):
    def __init__(self, question_text: str, short_name: str = None, choices: Union[List[str], Dict[str, str]]):
        super().__init__(question_text, short_name)
        self.choices =
            choices
            if isinstance(choices, dict)
            else {c: c for c in choices}
        self.choices_by_long_name = {
            text: name for name, text in self.choices.items()
        }
        self.length = len(self.choices)

    def clean(self, *response: str) -> Optional[str]:
        responses = [r for r in response if r]
        return self.choices_by_long_name[responses[0]] if responses else None

    def validate_heading(self, *head: str) -> bool:
        headers = set(head)
        return all((h in self.choices_by_long_name) for h in headers) and all((c in headers) for c in self.choices_by_long_name)

class MultiChoiceQuestion (ChoiceQuestion):
    def clean(self, *response: str) -> Dict[str, bool]:
        responses = set(r for r in response if r)
        return {name: (text in responses) for name, text in self.choices.items()}

class SurveyResponses (object):
    def __init__(self, questions: Iterable[SurveyQuestion], headers: List[str]):
        self.questions = list(itertools.chain(
            [MetaData.response_id],
            questions,
            [DateTimeQuestion.start, DateTimeQuestion.end, MetaData.network_id]))
        self.responses = {
            q.get_short_name(): [] for q in self.questions
        }
        self.mapping = []
        _temp_field_counter = 0
        for i, q in enumerate(self.questions):
            _end = _temp_field_counter + q.get_length()
            self.mapping[i] = slice(_temp_field_counter, _end)
            if not q.validate_heading(*headers[self.mapping[i]]):
                raise Exception(
                    'Could not confirm question "{text}" for headings {start} through {stop}. Check the question text or choice texts.'
                    .format(text = q.get_question_text, start = self.mapping[i].start, stop = self.mapping[i].stop)
                )
            _temp_field_counter = _end

    def ingest(*response: str):
        for i, q in enumerate(self.questions):
            self.responses[q.get_short_name()][i] = q.clean(*response[self.mapping[i]])

