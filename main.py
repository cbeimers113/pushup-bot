import os
import pickle
from datetime import date, datetime, timedelta

import discord
from discord.ext import tasks

intents = discord.Intents.all()
client = discord.Client(command_prefix='!', intents=intents)

# Map username to {day: [cumulative, debt, flag]}
# flag is whether this day's debt has been carried over to the next day
data: dict = {}

if os.path.exists('data.pkl'):
    with open('data.pkl', 'rb') as f:
        data = pickle.load(f)


@client.event
async def on_ready() -> None:
    """Perform actions on startup."""
    await client.change_presence(activity=discord.Game(name='help! for usage'))
    await debt_check.start()


@client.event
async def on_message(message: discord.Message) -> None:
    """Perform actions when a message is sent."""
    if message.author == client.user:
        if 'Cumulative: 100' in message.content:
            await message.add_reaction('💯')
        return

    mstr: str = message.content
    today: str = str(date.today())

    # If the message just contains a number (session count), log it
    if mstr.isnumeric() or mstr.startswith('-') and mstr[1:].isnumeric():
        user: str = message.author.name
        session: int = int(message.content)

        if user not in data:
            data[user] = {}

        if today not in data[user]:
            data[user][today] = [0, 0, False]

        if data[user][today][0] < 100:

            # Pay off debt first, then accumulate new pushups
            if data[user][today][1] > 0:
                data[user][today][1] -= session

                # Carry over extra payment to cumulative
                if data[user][today][1] < 0:
                    delta = abs(data[user][today][1])
                    data[user][today][0] += delta
                    data[user][today][1] = 0

            else:
                data[user][today][0] += session

                # If cumulative goes negative, add it to debt
                if data[user][today][0] < 0:
                    delta = abs(data[user][today][0])
                    data[user][today][0] = 0
                    data[user][today][1] += delta

            # Clamp to 100 pushups for the day
            data[user][today][0] = min(100, data[user][today][0])
            response: str = f'{message.author.mention}\nSession: {session}\nCumulative: {data[user][today][0]}'

            if data[user][today][1]:
                response += f'\nDebt: {data[user][today][1]}'

            await message.channel.send(response)

        else:
            await message.channel.send(f"{message.author.mention}, stop! You're done for the day\n(Bonus session: {session})")

        await message.delete()

    # Print the help message
    elif mstr == 'help!':
        await message.channel.send('Simply send your session count in a message\nUse a negative count to undo')


@tasks.loop(minutes=1)
async def debt_check() -> None:
    """Run every day at midnight, carries over debt to the next day."""
    today = str(date.today())
    yesterday = str(date.today() - timedelta(days=1))

    if datetime.now().hour == 0:
        for user in data:
            if today not in data[user]:
                data[user][today] = [0, 0, False]

            if yesterday in data[user] and not data[user][yesterday][2]:
                debt = 100 - data[user][yesterday][0]
                data[user][today][1] = data[user][yesterday][1] + debt
                data[user][yesterday][2] = True

with open('token.txt', 'r') as f:
    client.run(f.read())

if data:
    with open('data.pkl', 'wb') as f:
        pickle.dump(data, f)
