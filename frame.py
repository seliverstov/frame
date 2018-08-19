import random
from typing import List, Callable, Union
from collections import defaultdict
import json
import sys
import logging

REGISTRY = {}


class Frame(object):

    def __init__(self, ner='simple_slot_fill'):
        self._deeppavlov_slot = '_deeppavlov_slot'
        logging.debug(ner)

    def __call__(self, frame_cls, *args, **kwargs):
        global REGISTRY
        self.frame_cls = frame_cls
        self.frame_name = frame_cls.__name__
        REGISTRY[self.frame_name] = {}
        logging.debug(f"Frame '{self.frame_name}' added to global registry")
        for name, obj in self.frame_cls.__dict__.items():
            if hasattr(obj, self._deeppavlov_slot):
                if name in REGISTRY[self.frame_name]:
                    raise Exception(f"Slot '{name}' already registered for frame '{self.frame_name}'")
                REGISTRY[self.frame_name][name] = getattr(obj, self._deeppavlov_slot)
                logging.debug(f"Slot '{name}' was registered for frame '{self.frame_name}'")
        return frame_cls

    @staticmethod
    def slot(requester: Union[str, List, Callable], extractor: Union[str, Callable],
             updater: Union[str, Callable]='replace',
             validator: Callable=None):

        if type(requester) == str:
            r = lambda: requester
        elif type(requester) == list:
            r = lambda: random.choice(requester)
        else:
            r = requester

        if type(extractor) == str:
            e = lambda entities: entities[extractor]
        else:
            e = extractor

        if type(updater) == str:
            if updater == 'replace':
                u = lambda s, v: v
            elif updater == 'append':
                u = lambda s, v: s + v
        else:
            u = updater

        if validator is None:
            v = lambda v: (True, None)
        else:
            v = validator

        def _wrapper(field):
            field._deeppavlov_slot = {
                'value': '',
                'requester': r,
                'extractor': e,
                'updater': u,
                'validator': v
            }
            return field
        return _wrapper



@Frame('DSTC2_NER')
class ProductInfoFrame(object):

    @Frame.slot("Уточните, по какому продукту нужна информация?", "PRODUCT")
    def product(self):
        pass

    @Frame.slot("Уточните, из какого вы региона?", "REGION")
    def region(self):
        pass

    def __call__(self, entities, *args, **kwargs):
        global REGISTRY
        slots = REGISTRY[self.__class__.__name__]
        to_request = []
        invalid = []
        updated = []
        for name, slot in slots.items():
            logging.debug(f"Process slot '{name}'")
            value = slot['extractor'](entities)
            logging.debug(f"Extract new value: '{value}'")
            if not value and not slot['value']:
                logging.debug(f"Request value for slot: '{name}'")
                to_request.append({name: slot['requester']()})
            else:
                valid, msg = slot['validator'](value)
                if not valid:
                    logging.debug(f"Slot value is invalid: {msg}")
                    invalid.append({name: msg})
                else:
                    new_value = slot['updater'](slot['value'], value)
                    slot['value'] = new_value
                    updated.append({name: new_value})
                    logging.debug(f"Slot value was set to : {slot['value']}")

        if to_request:
            return to_request[0]
        elif invalid:
            return invalid[0]
        else:
            state = {}
            for name, slot in slots.items():
                state[name] = slot['value']
            return f"FRAME: {state}"


if __name__ == "__main__":
    p = ProductInfoFrame()
    for line in sys.stdin:
        entities = defaultdict(str)
        j = json.loads(line)
        entities.update(j)
        print(p(entities))
