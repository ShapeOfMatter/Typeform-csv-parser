#!/usr/bin/env python3

import csv
import datetime
import itertools
import re
from typing import Dict, Iterable, List, Optional, Union

class SurveyQuestion (object):
    def __init__(self):
        raise NotImplementedError( "SurveyQuestion is abstract; it can not be instantiated." )

    def get_question_text(self) -> str:
        return self.question_text

    def get_short_name(self) -> str:
        return self.short_name

    def get_length(self) -> int:
        return self.length

    def clean(self, *response: str):
        return ''.join(response)

    def validate_heading(self, *head: str) -> bool:
        return head and head[0].strip() and self.get_question_text() == head[0].strip()

    def easy_summary(self, responses) -> Dict[str, str]:
        return {
            'Count': str(len(responses)),
        }

class _BaseQuestion (SurveyQuestion):
    def __init__(self, question_text: str, short_name: str = None):
        self.question_text = question_text.strip()
        self.short_name = short_name.strip() if short_name else self.question_text
        self.length = 1

class TextQuestion (_BaseQuestion):
    def easy_summary(self, responses) -> Dict[str, str]:
        return {
            'Count': str(len([r for r in responses if r])),
        }

class MetaData (_BaseQuestion):
    pass

_response_id = MetaData('#', 'ID')
_network_id = MetaData('Network ID')

class DateTimeQuestion (_BaseQuestion):
    def clean(self, *response: str) -> Optional[datetime.datetime]:
        return datetime.datetime.strptime(response[0].strip(), '%Y-%m-%d %H:%M:%S') if response and response[0].strip() else None

    def easy_summary(self, responses: Iterable[Optional[datetime.datetime]]) -> Dict[str, str]:
        filtered = [r for r in responses if r]
        return {
            'Count': str(len(filtered)),
            'Earliest': str(min(filtered).isoformat()),
            'Latest': str(max(filtered).isoformat()),
        }
    
_start_time = DateTimeQuestion('Start Date (UTC)', 'Start Date')
_end_time = DateTimeQuestion('Submit Date (UTC)', 'End Date')

class IntegerQuestion (_BaseQuestion):
    def clean(self, *response: str) -> Optional[int]:
        return int(response[0]) if response and response[0] else None

    def easy_summary(self, responses: Iterable[Optional[Union[int, float]]]) -> Dict[str, str]:
        filtered = [r for r in responses if r is not None]
        return {
            'Count': str(len(filtered)),
            'Min': str(min(filtered)),
            'Mean': str(sum(filtered) / float(len(filtered))),
            'Max': str(max(filtered)),
        }

class FreeNumberQuestion (IntegerQuestion):
    reg = re.compile('^[^0-9.]*([0-9.]+)[^0-9.]*$')
    def clean(self, *response: str) -> Optional[float]:
        if (not response) or (not response[0]):
            return None
        m = self.reg.match(response[0])
        if m is None:
            print('Failed to parse response "{}" to question "{}".'.format(response[0], self.short_name))
            return None
        else:
            return float(m.group(1))

class BoolQuestion (IntegerQuestion):
    def clean(self, *response: str) -> Optional[bool]:
        num = super().clean(*response)
        return None if num is None else bool(num)

    def easy_summary(self, responses: Iterable[Optional[bool]]) -> Dict[str, str]:
        filtered = [r for r in responses if r is not None]
        return {
            'Count': str(len(filtered)),
            'Yes': str(sum(filtered)),
            'No': str(sum(1 for b in filtered if not b)),
        }

class ChoiceQuestion (_BaseQuestion):
    def __init__(self, question_text: str, choices: Union[List[str], Dict[str, str]], short_name: str = None):
        super().__init__(question_text, short_name)
        self.choices = (
            {name.strip(): text.strip()
             for name, text in choices.items()}
            if isinstance(choices, dict)
            else {c.strip(): c.strip()
                  for c in choices}
        )
        self.choices_by_long_name = {
            text: name for name, text in self.choices.items()
        }

    def clean(self, *response: str) -> Optional[str]:
        return self.choices_by_long_name[response[0].strip()] if response and response[0].strip() else None

    def easy_summary(self, responses: Iterable[Optional[str]]) -> Dict[str, str]:
        filtered = [r for r in responses if r]
        retval = {'Count': str(len(filtered)) }
        retval.update({
            c: str(len([f for f in filtered if f == c]))
            for c in self.choices.keys()
        })
        return retval

class MultiChoiceQuestion (ChoiceQuestion):
    def __init__(self, *args):
        super().__init__(*args)
        self.length = len(self.choices)
    
    def clean(self, *response: str) -> Dict[str, bool]:
        responses = set(r.strip() for r in response if r)
        return {name: (text in responses) for name, text in self.choices.items()}

    def validate_heading(self, *head: str) -> bool:
        headers = set(header.strip() for header in head)
        return all((h in self.choices_by_long_name) for h in headers) and all((c in headers) for c in self.choices_by_long_name)
    
    def easy_summary(self, responses: Iterable[Dict[str, bool]]) -> Dict[str, str]:
        filtered = [r for r in responses if any(r.values())]
        retval = {'Count': str(len(filtered)) }
        retval.update({
            c: str(len([f for f in filtered if f[c]]))
            for c in self.choices.keys()
        })
        return retval

class SurveyResponses (object):
    def __init__(self, questions: Iterable[SurveyQuestion], headers: List[str]):
        self.questions = list(itertools.chain(
            [_response_id],
            questions,
            [_start_time, _end_time, _network_id]))
        self.responses = {
            q.get_short_name(): [] for q in self.questions
        }
        self.mapping = [None for _ in self.questions]
        _temp_field_counter = 0
        for i, q in enumerate(self.questions):
            _end = _temp_field_counter + q.get_length()
            self.mapping[i] = slice(_temp_field_counter, _end)
            if not q.validate_heading(*headers[self.mapping[i]]):
                raise Exception(
                    'Could not confirm question "{text}" for headings "{start}" through "{stop}". Check the question text or choice texts.'
                    .format(text = q.get_question_text(), start = headers[self.mapping[i].start], stop = headers[self.mapping[i].stop - 1])
                )
            _temp_field_counter = _end

    def ingest(self, *response: str):
        for i, q in enumerate(self.questions):
            self.responses[q.get_short_name()].append(q.clean(*response[self.mapping[i]]))


def parse( survey: Iterable[SurveyQuestion] , results: Iterable[List[str]] ) -> SurveyResponses:
    results_iter = iter(results)
    retval = SurveyResponses(survey, next(results_iter))
    for r in results_iter:
        retval.ingest(*r)
    return retval


