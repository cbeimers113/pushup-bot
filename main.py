import os
import pickle
from datetime import date, datetime, timedelta

import discord
from discord.ext import tasks

intents = discord.Intents.all()
client = discord.Client(command_prefix='!', intents=intents)

# Map username to {day: [cumulative, debt, debt_check, warn]}
# day: the record's date
# cumulative: how many pushups the user has done on day
# debt: how many pushups the user has missed on previous days, will accumulate first
# debt_check: whether yesterday's debt has been carried forward for this user
# warn: whether this user has been warned that time is running out for the day
data: dict = {}
msg_channel = discord.utils.get(client.get_all_channels(), name='General')

if os.path.exists('data.pkl'):
    with open('data.pkl', 'rb') as f:
        data = pickle.load(f)


@client.event
async def on_ready() -> None:
    """Perform actions on startup."""
    await client.change_presence(activity=discord.Game(name='help! for usage'))
    await timed_tasks.start()
    await msg_channel.send('💪')


@client.event
async def on_message(message: discord.Message) -> None:
    """Perform actions when a message is sent."""
    if message.author == client.user:
        if 'Cumulative: 100' in message.content:
            await message.add_reaction('💯')
        return

    mstr: str = message.content
    today: str = str(date.today())
    user: str = message.author.name

    # If the message just contains a number (session count), log it
    if mstr.isnumeric() or mstr.startswith('-') and mstr[1:].isnumeric():
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
        await message.channel.send('Simply send your session count in a message\nUse a negative count to undo\nUse "?" to see your stats for today.')

    # Show stats for the day for the user
    elif mstr == '?':
        await message.channel.send(f'{message.author.mention}\nYour pushups for {today}:\nCumulative: {data[user][today][0]}\nDebt: {data[user][today][1]}')


@tasks.loop(minutes=0.5)
async def timed_tasks() -> None:
    """Run scheduled tasks."""
    today: str = str(date.today())
    yesterday: str = str(date.today() - timedelta(days=1))
    hour: int = datetime.now().hour
    minute: int = datetime.now().minute

    # Carry over debt to the next day at midnight
    if hour == 0 and minute == 0:
        for user in data:
            if today not in data[user]:
                data[user][today] = [0, 0, False]

            if yesterday in data[user] and not data[user][yesterday][2]:
                debt = 100 - data[user][yesterday][0]
                data[user][today][1] = data[user][yesterday][1] + debt
                data[user][yesterday][2] = True

            print(data[user][yesterday])
            print('↓')
            print(data[user][today])
            print(flush=True)

    # Snap fingers at anyone who needs to do more pushups at 12:30
    if hour == 23 and minute == 30:
        warn_msg = '🫰🫰' + '\n'.join([
            user.mention for user in msg_channel.members if data[user.name][today][0] < 100
        ])

        await msg_channel.send(warn_msg)

with open('token.txt', 'r') as f:
    client.run(f.read())

if data:
    with open('data.pkl', 'wb') as f:
        pickle.dump(data, f)
