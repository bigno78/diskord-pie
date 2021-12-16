# diskord-pie

A simple and incomplete wrapper around the discord api. Currently it is in state of development so it is even more incomplete then planned.

## Disclaimer

You probably shouldn't use this library. If you use it, it is at your own risk. It implements only a very limited part of the discord api and what it implements is most likely wrong.

## Why does it exist then?

To be honest, I don't know. Probably because I am insane.

## Installing

If you are still here and for some unknown reason want to install the library, here is how. Since I don't intent for other people to use it, it is not on PyPi. But u can still install it by just cloning this repo and running the following command in the root directory.

```bash
$ python -m pip install .
```

## Example usage

The following code shows how a simple slash command can be created.

```python3
import diskordpie


bot = diskordpie.Bot()


@bot.slash_command(
    description="Ping it baby!"
)
async def ping(interaction, thing: str):
    await interaction.respond(thing)

if __name__ == "__main__":
    bot.run("your-token")
```

To define a slash command you have to annotate an *async* function with the `@bot.slash_command()` annotation. The first argument to that function is always an interaction object representing the particular invocation of the command. The remaining arguments are the options of the command. They need to have type annotations so the proper type can be reported to discord. Currently only these types are supported: `int`, `float`, `str`.
