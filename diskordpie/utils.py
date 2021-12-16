import json
import inspect
from enum import Enum

def to_dict(obj):
    res = {}
    
    for k in obj.__dict__:
        if k.startswith("_") or k.endswith("_"):
            continue
        
        thing = obj.__dict__[k]
        if inspect.ismethod(thing):
            continue

        if isinstance(thing, list):
            arr = []
            for val in thing:
                if inspect.isbuiltin(val):
                    arr.append(val)
                else:
                    arr.append(to_dict(val))
            res[k] = arr
            continue
        
        module = inspect.getmodule(thing)
        #print(k, module)

        # recursively serialize only classes from our library
        if module and module.__name__.startswith("diskordpie"):
            thing = to_dict(thing)

        res[k] = thing

    return res

def to_json(obj, indent=None):
    return json.dumps(to_dict(obj), indent=indent)
