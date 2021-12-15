from enum import Enum
import inspect

__all__ = [ "OptionType", "Option", "SlashCommand" ]

class OptionType(Enum):
    SUB_COMMAND = 1	
    SUB_COMMAND_GROUP = 2	
    STRING = 3	
    INTEGER = 4	
    BOOLEAN = 5	
    USER = 6	
    CHANNEL = 7	
    ROLE = 8	
    MENTIONABLE = 9	
    NUMBER = 10	

    def to_json(self):
        return self.value()

class Option:

    def __init__(self, **kwargs) -> None:
        self.type = kwargs.get("type")
        self.name = kwargs.get("name")
        self.description = kwargs.get("description", "")
        self.required = kwargs.get("required")
        self.choices = kwargs.get("choices")
        self.options = kwargs.get("options")
        self.channel_types = kwargs.get("channel_types")
        self.min_value = kwargs.get("min_value")
        self.max_value = kwargs.get("max_value")
        self.autocomplete = kwargs.get("autocomplete")
        self._arg_name = kwargs.get("arg_name")

    @staticmethod
    def Range(start, end, **kwargs):
        args = {
            "min_value": start,
            "max_value": end,
        }
        return Option(**args, **kwargs)


class SlashCommand:

    _type_map = {
        int: OptionType.INTEGER,
        float: OptionType.NUMBER,
        str: OptionType.STRING,
        bool: OptionType.BOOLEAN,
    }

    def __init__(self, func, *, name=None, description=None, options=None) -> None:
        self._func = func
        self.name = name if name else func.__name__
        self.description = description
        self.options = []

        sig = inspect.signature(func)

        is_first = True
        for arg_name, param in sig.parameters.items():
            # skip the first one since that is the interaction parameter
            # and not a command option
            if is_first:
                is_first = False
                continue

            if options and arg_name in options:
                opt = options[arg_name]
                opt.arg_name = arg_name
            else:
                opt = Option(arg_name=arg_name)

            if not opt.name:
                opt.name = arg_name

            if not opt.type:
                annot = param.annotation
                if annot == inspect.Parameter.empty:
                    raise Exception(f"Cannot deduce type for option {arg_name}")
                if not annot in SlashCommand._type_map:
                    raise Exception(f"Unknown type for option {arg}")
                opt.type = SlashCommand._type_map[annot]
            
            if not opt.required:
                opt.required = param.default == inspect.Parameter.empty

            self.options.append(opt)

    async def invoke(self, interaction, **kwargs):
        await self._func(interaction, **kwargs)

    async def __call__(self, interaction, **kwargs):
        await self.invoke(interaction, **kwargs)
