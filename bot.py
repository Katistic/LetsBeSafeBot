import discord
import asyncio
import aiohttp
import random
import time
import os

from iomanage import IOManager as IOM
import urllib.parse
import youtube_dl

ytdl = youtube_dl.YoutubeDL({
    'format': 'bestaudio/best',
    'outtmpl': 'lbs-%(extractor)s-%(id)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no-cache-dir': True,
    'no_warnings': True,
    "rm-cache-dir": True,
    #"verbose": True,
    'default_search': 'auto'
})

ffmpeg_options = {
    'options': '-vn'
}

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

        self.bFilename = "lbs-"+data.get('extractor')+"-"+data.get('id')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=None):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        # Redundant due to noplaylist param
        '''
        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]
        '''

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

    @classmethod
    async def url_from_query(self, q):
        async with aiohttp.ClientSession() as session:
            async with session.get("https://www.googleapis.com/youtube/v3/search?part=snippet&maxResults=1&q="+urllib.parse.quote(q)+"&type=video&key="+io.read()["ytToken"]) as d:
                d = await d.json()
                return "https://www.youtube.com/watch?v="+d["items"][0]["id"]["videoId"]

    @classmethod
    async def urls_from_playlist_id(self, id, all=True, npt=None):
        async with aiohttp.ClientSession() as session:
            if npt == None:
                async with session.get("https://www.googleapis.com/youtube/v3/playlistItems?part=contentDetails&maxResults=50&playlistId="+id+"&key="+io.read()["ytToken"]) as d:
                    if d.status != 200:
                        return []
                    d = await d.json()
            else:
                async with session.get("https://www.googleapis.com/youtube/v3/playlistItems?part=contentDetails&maxResults=50&pageToken="+npt+"&playlistId="+id+"&key="+io.read()["ytToken"]) as d:
                    if d.status != 200:
                        return []
                    d = await d.json()

        items = []

        for item in d["items"]:
            items.append("https://www.youtube.com/watch?v="+item["contentDetails"]["videoId"])

        if all == True and "nextPageToken" in d:
            items += await self.urls_from_playlist_id(id, all, d["nextPageToken"])

        return items

class Bot(discord.Client):
    def removeFile(self, base):
        removed = False
        print("[BOT] Removing "+base)

        for root, dirs, files in os.walk("."):
            for file in files:
                if base in file:
                    os.remove(os.path.join(root, file))
                    removed = True
                    break
            if removed: break

        return removed

    def removeOldSongs(self):
        print("[BOT] Removing old songs...")

        for root, dirs, files in os.walk("."):
            for file in files:
                if file.startswith("lbs-"):
                    os.remove(file)
                    print("[BOT] Removed "+file)

    async def playerLoop(self):
        self.playerLoopRunning = True

        while len(self.Queue) != 0 and self.VoiceClient != None:
            await asyncio.sleep(1)

            if self.VoiceClient.is_playing():
                continue

            if self.Player != None:
                self.removeFile(self.Player.bFilename)

            try:
                self.Player = await YTDLSource.from_url(self.Queue.pop(0), loop=self.loop, stream=False)
                self.VoiceClient.play(self.Player, after=lambda e: print('[BOT] Player error: %s' % e) if e else None)
                await asyncio.sleep(5)
            except Exception as e:
                self.VoiceClient.stop()
                print(e)

        self.playerLoopRunning = False

    ## Command functions

    async def tst_cmd(self, msg, parts):
        await msg.channel.send(msg.author.mention+", bot is recieving commands.")

    async def hlp_cmd(self, msg, parts):

        # Is the user asking for help for a specific command?
        if len(parts) == 2: # Yes
            cmd = self.search_command(parts[1])
            if not cmd == None:
                descs = "Help for `"+cmd["name"]+"`:\n  Alias: "
                descs += ", ".join[cmd['alias']] if len(cmd['alias']) > 0 else "None"
                descs += "\n  Description: "+cmd['description']
                await msg.channel.send(msg.author.mention+"\n\n"+descs)
            else: # Command doesn't exist
                await msg.channel.send("{}\nCommand '{}' does not exist.".format(msg.author.mention, parts[1]))
        else: # No
            descs = msg.author.mention + " Command List\n\n"
            for command in self.Commands:
                descs += "`"+command['name']+"`:\n  Alias: "
                descs += ", ".join[command['alias']] if len(command['alias']) > 0 else "None"
                descs += "\n  Description: "+command['description']
                if self.Commands.index(command) != self.Commands[-1]: descs += "\n\n"

            await msg.channel.send(descs)

    async def priv_check_cmd(self, msg, parts):
        member = msg.author
        if await self.chck_usr_dir_msg(member, obj=True):
            try:
                await self.remove_member_role(member, 632518235987902485, obj=True)
            except:
                pass
        else:
            try:
                await self.give_member_role(member, 632518235987902485, obj=True)
            except:
                pass

    # Audio

    async def join_cmd(self, msg, parts):
        if msg.author.voice != None:
            if self.VoiceClient == None or not self.VoiceClient.is_connected():
                self.VoiceClient = await msg.author.voice.channel.connect()
                await msg.channel.send("Joined into "+msg.author.voice.channel.name)

                return True
            elif self.VoiceClient.channel != msg.author.voice.channel:
                await self.VoiceClient.move_to(msg.author.voice.channel)
                await msg.channel.send("Moved into "+msg.author.voice.channel.name)
        else:
            await msg.channel.send(msg.author.mention+", you aren't in a voice channel.")

        return False

    async def leave_cmd(self, msg, parts):
        if self.VoiceClient != None and self.VoiceClient.is_connected():
            if msg.author.voice.channel == self.VoiceClient.channel:
                await self.VoiceClient.disconnect()
                self.VoiceClient.stop()
                self.Queue.clear()
                self.VoiceClient = None
                await msg.channel.send("Left voice channel.")
            else:
                await msg.channel.send(msg.author.mention+", the bot isn't in the same voice channel as you.")
        else:
            await msg.channel.send(msg.author.mention+", the bot isn't in a voice channel.")

    async def play_cmd(self, msg, parts):
        if msg.author.voice != None:
            if self.VoiceClient == None or msg.author.voice.channel != self.VoiceClient.channel:
                await self.join_cmd(msg, parts)

            # TODO: Fix this check up
            if self.VoiceClient != None and self.VoiceClient.is_connected() and msg.author.voice.channel == self.VoiceClient.channel:
                if len(parts) > 1:
                    if len(parts) == 2 and parts[1].count(" ") == 0 and "." in parts[1] and "/" in parts[1]:
                        url = parts[1]
                        self.Queue.append(url)
                        await msg.channel.send("Added song to the queue.")
                    else:
                        del parts[0]

                        q = " ".join(parts)
                        url = await YTDLSource.url_from_query(q)
                        self.Queue.append(url)

                        await msg.channel.send("Added song to the queue: "+url)

                    if not self.playerLoopRunning:
                        self.loop.create_task(self.playerLoop())
            else:
                await msg.channel.send(msg.author.mention+", the bot isn't in the same voice channel as you.")
        else:
            await msg.channel.send(msg.author.mention+", the bot isn't in a voice channel.")

    async def skip_cmd(self, msg, parts):
        if self.VoiceClient != None and self.VoiceClient.is_connected():
            if self.VoiceClient.channel == msg.author.voice.channel:
                if self.VoiceClient.is_playing():
                    self.VoiceClient.stop()
                    await msg.channel.send("Skipping song...")
                else:
                    await msg.channel.send("Nothing is playing.")
            else:
                await msg.channel.send("You are not in the voice channel with me.")
        else:
            await msg.channel.send("I'm not in a voice channel.")

    async def remove_cmd(self, msg, parts):
        if self.VoiceClient != None and self.VoiceClient.is_connected():
            if self.VoiceClient.channel == msg.author.voice.channel:
                if len(parts) == 2:
                    url = parts[1]
                    if url in self.Queue:
                        self.Queue.remove(url)
                        await msg.channel.send("Removed song from queue.")
                    else:
                        await msg.channel.send("That URL is not in the queue.")
                else:
                    await msg.channel.send("Please enter a URL to remove from queue.")
            else:
                await msg.channel.send("You are not in the voice channel with me.")
        else:
            await msg.channel.send("I'm not in a voice channel.")

    async def shuffle_cmd(self, msg, parts):
        if self.VoiceClient != None and self.VoiceClient.is_connected():
            if self.VoiceClient.channel == msg.author.voice.channel:
                random.shuffle(self.Queue)
                print("[USR] Shuffled queue")
                await msg.channel.send("Queue was shuffled.")
            else:
                await msg.channel.send("You are not in the voice channel with me.")
        else:
            await msg.channel.send("I'm not in a voice channel.")

    async def playlist_cmd(self, msg, parts):
        vc = True

        if msg.author.voice != None:
            if self.VoiceClient == None or msg.author.voice.channel != self.VoiceClient.channel:
                vc = await self.join_cmd(msg, parts)

            if vc:
                if len(parts) == 2 and parts[1].count(" ") == 0 and "." in parts[1] and "/" in parts[1] and "youtube.com" in parts[1] and "list=" in parts[1]:
                    id = parts[1].split("list=")[1]
                    id = id.split("&")[0] if "&" in id else id

                    items = await YTDLSource.urls_from_playlist_id(id, True)
                    self.Queue += items

                    await msg.channel.send("Added {} song(s) to the queue.".format(str(len(items))))

                    if not self.playerLoopRunning:
                        self.loop.create_task(self.playerLoop())
                else:
                    await msg.channel.send("Please enter a valid youtube playlist url.")
            else:
                await msg.channel.send("You are not in the voice channel with me.")
        else:
            await msg.channel.send("You are not in the voice channel with me.")

    ## Utility funcs

    def __init__(self):
        super().__init__()

        self.Commands = []
        self.Newbies = []
        self.Queue = []
        self.VoiceClient = None
        self.Player = None

        self.playerLoopRunning = False

        ## Comman
        self.create_command(
            "test",
            self.tst_cmd,
            "Test to see if bot is recieving commands.",
            roles = [
                632518235987902485
            ]
        )

        self.create_command(
            "help",
            self.hlp_cmd,
            "List commands and their descriptions, or use ***{}help <command>*** to describe a specific command.".format(io.read()['prefix'])
        )

        self.create_command(
            "check",
            self.priv_check_cmd,
            "Check if you are compliant with servers privacy policy, and assign role accordingly."
        )

        self.create_command(
            "join",
            self.join_cmd,
            "Makes bot join your current voice channel."
        )

        self.create_command(
            "leave",
            self.leave_cmd,
            "Makes bot leave your voice channel."
        )

        self.create_command(
            "play",
            self.play_cmd,
            "Plays a song. Supports most sites except spotify (via url). ***{}play <url/songname>***".format(io.read()['prefix'])
        )

        self.create_command(
            "skip",
            self.skip_cmd,
            "Skips a song."
        )

        self.create_command(
            "remove",
            self.remove_cmd,
            "Removes URL from queue. ***{}remove <url>***".format(io.read()['prefix'])
        )

        self.create_command(
            "shuffle",
            self.shuffle_cmd,
            "Shuffles queue."
        )

        self.create_command(
            "playlist",
            self.playlist_cmd,
            "Adds a playlist from youtube to the queue. ***{}playlist <url>***".format(io.read()['prefix'])
        )

        self.removeOldSongs()
        self.run(io.read()['clientToken'])

    # Search for command, returns command dict
    def search_command(self, name):
        name = name.lower()
        for command in self.Commands:
            if command['name'] == name or name in command['alias']:
                return command
        return None

    # Create a command
    def create_command(self, name, function, description, roles=[], alias=[], asyncio=True):
        command = {
            "name": name,
            "function": function,
            "roles": roles,
            "alias": alias,
            "description": description,
            "asyncio": asyncio
        }

        # Check for replica command names
        isNew = True
        taken = []
        if not self.search_command(name) == None:
            isNew = False
            taken.append(name)
        for a in alias:
            if not self.search_command(a) == None:
                isNew = False
                taken.append(a)

        if isNew:
            self.Commands.append(command)
        else: # Command name/alias taken
            raise Exception("Name/Alias already used in CreateCommand: %s" % ", ".join(taken))

    # Removes member role of roleid
    # if obj=True it means mem is obj, not id
    async def remove_member_role(self, mem, roleid, obj=False):
        # Get this server
        for guild in self.guilds:
            if guild.id == 632460050660720650:
                break

        # If obj=False get mem
        if obj==False:
            mem = guild.get_member(mem)

        # Get role
        if type(roleid) == int:
            role = guild.get_role(roleid)
            await mem.remove_roles(role)
        else:
            role = []
            for rid in roleid:
                role.append(guild.get_role(rid))

            await mem.remove_roles(*role)

    # Gives member role of roleid
    # if obj=True it means mem is obj, not id
    async def give_member_role(self, mem, roleid, obj=False):
        # Get this server
        for guild in self.guilds:
            if guild.id == 632460050660720650:
                break

        # If obj=False get mem
        if obj==False:
            mem = guild.get_member(mem)

        # Get role
        if type(roleid) == int:
            role = guild.get_role(roleid)
            await mem.add_roles(role)
        else:
            role = []
            for rid in roleid:
                role.append(guild.get_role(rid))

            await mem.add_roles(*role)

    # Check if direct messages are enabled for a user
    # obj=False means user is id
    async def chck_usr_dir_msg(self, member, obj=False):
        # Get user obj if user is id
        if obj==False:
            for guild in self.guilds:
                if guild.id == 632460050660720650:
                    member = guild.get_member(member)
                    break

        # Try send message to user
        # Will fail if direct messages disabled
        try:
            await member.send("Please disable direct messages to gain access to channels!\nYou can check how to do this in <#632517617541709826>.")
            return True
        except:
            return False

    ### Privacy Check Loop

    async def priv_check_loop(self):
        for guild in self.guilds:
            if guild.id == 632460050660720650:
                break

        while True:
            print('[BOT] Doing routine privacy check')
            async for member in guild.fetch_members(limit=None):
                if member.id in self.Newbies:
                    self.Newbies.remove(member.id)
                    continue

                if await self.chck_usr_dir_msg(member, obj=True):
                    try:
                        await self.remove_member_role(member, 632518235987902485, obj=True)
                    except:
                        pass
                else:
                    try:
                        await self.give_member_role(member, 632518235987902485, obj=True)
                    except:
                        pass
                time.sleep(2) # Don't hit the rate limit

            await asyncio.sleep(300)

    def cmd_authorized(self, cmd, usr):
        usrr = []

        for role in usr:
            usrr.append(role.id)

        for role in cmd:
            if not role in usrr:
                return False

        return True

    ### Events

    async def on_member_join(self, mem):
        if mem.guild.id == 632460050660720650:
            print("[USR] Joined server")
            if await self.chck_usr_dir_msg(mem, obj=True):
                self.Newbies.append(mem.id)
            else:
                await self.give_member_role(mem, 632518235987902485, obj=True)

    async def on_raw_reaction_add(self, payload):
        if payload.guild_id == 632460050660720650:
            if payload.message_id == 632527260859236373:
                if payload.emoji.id == 590028329277718538:
                    print("[USR] Obtained gender role 'male'")
                    await self.give_member_role(payload.user_id, 632522224024289301)
                elif payload.emoji.id == 476801025991507979:
                    print("[USR] Obtained gender role 'everything'")
                    await self.give_member_role(payload.user_id, 632522554074071050)
                elif payload.emoji.id == 527053057171783690:
                    print("[USR] Obtained gender role 'nothing'")
                    await self.give_member_role(payload.user_id, 632524877412171788)
                elif payload.emoji.id == 590028360772616193:
                    print("[USR] Obtained gender role 'female'")
                    await self.give_member_role(payload.user_id, 632522281888776202)
                elif payload.emoji.id == 616113741980893214:
                    print("[USR] Obtained gender role 'other'")
                    await self.give_member_role(payload.user_id, 699339137639120971)
                else:
                    print("[USR] Unknown gender reaction ("+str(payload.emoji.id)+")")

            elif payload.message_id == 632528504319377449:
                if payload.emoji.id == 556161748822917120:
                    print("[USR] Obtained age role '18+'")
                    await self.give_member_role(payload.user_id, 632525773756170260)
                elif payload.emoji.id == 533032578165506058:
                    print("[USR] Obtained age role '<18'")
                    await self.give_member_role(payload.user_id, 632516288111050752)
                else:
                    print("[USR] Unknown age reaction ("+str(payload.emoji.id)+")")


    async def on_raw_reaction_remove(self, payload):
        if payload.guild_id == 632460050660720650:
            if payload.message_id == 632527260859236373:
                if payload.emoji.id == 590028329277718538:
                    print("[USR] Removed gender role 'male'")
                    await self.remove_member_role(payload.user_id, 632522224024289301)
                elif payload.emoji.id == 476801025991507979:
                    print("[USR] Removed gender role 'everything'")
                    await self.remove_member_role(payload.user_id, 632522554074071050)
                elif payload.emoji.id == 527053057171783690:
                    print("[USR] Removed gender role 'nothing'")
                    await self.remove_member_role(payload.user_id, 632524877412171788)
                elif payload.emoji.id == 590028360772616193:
                    print("[USR] Removed gender role 'female'")
                    await self.remove_member_role(payload.user_id, 632522281888776202)
                elif payload.emoji.id == 616113741980893214:
                    print("[USR] Removed gender role 'other'")
                    await self.remove_member_role(payload.user_id, 699339137639120971)
                else:
                    print("[USR] Unknown gender reaction ("+str(payload.emoji.id)+")")
            elif payload.message_id == 632528504319377449:
                if payload.emoji.id == 556161748822917120:
                    print("[USR] Removed age role '18+'")
                    await self.remove_member_role(payload.user_id, 632525773756170260)
                elif payload.emoji.id == 533032578165506058:
                    print("[USR] Removed age role '<18'")
                    await self.remove_member_role(payload.user_id, 632516288111050752)
                else:
                    print("[USR] Unknown age reaction ("+str(payload.emoji.id)+")")


    async def on_message(self, msg):
        if not msg.author.bot:
            if msg.channel.guild.id == 632460050660720650:
                pf = io.read()['prefix']
                if msg.content.startswith(pf):
                    parts = msg.content[len(pf):].split(" ")
                    command = self.search_command(parts[0])
                    if command != None:
                        if self.cmd_authorized(command["roles"], msg.author.roles):
                            print("[USR] Sent command in "+msg.channel.name+" ("+str(msg.channel.id)+")")
                            if command["asyncio"]:
                                await command["function"](msg, parts)
                            else:
                                command["function"](msg, parts)
                        else:
                            print("[USR] Sent unauthorized command in "+msg.channel.name+" ("+str(msg.channel.id)+")")
                    else:
                        print("[USR] Sent invalid command in "+msg.channel.name+" ("+str(msg.channel.id)+")")

        if msg.channel.id == 691821269460582503:
            await msg.delete(delay=5)

    async def on_connect(self):
        print("[BOT] Logged in as %s" % self.user.name)

    async def on_disconnect(self):
        print("[BOT] Connection to discord terminated")

    async def on_ready(self):
        print("[BOT] Internal cache is ready")

        # Start privacy check loop
        self.loop.create_task(self.priv_check_loop())
        #await asyncio.ensure_future(self.priv_check_loop())

    async def on_resumed(self):
        print("[BOT] Connection to discord re-established")

    async def on_voice_state_update(self, member, b, a):
        if self.VoiceClient != None and self.VoiceClient.channel != None:
            if len(self.VoiceClient.channel.members) == 1 and self.member.guild.me in self.VoiceClient.channel.members:
                await self.VoiceClient.channel.guild.get_channel(632591366400245787).send("Everyone left the voice channel, queue has been cleared.")
                self.Queue.clear()
                self.VoiceClient.stop()
                await self.VoiceClient.disconnect()
                self.VoiceClient = None

    '''
    async def on_error(self, event, *args, **kwargs):
        print("[ERR] Bot failed on event '" + event + "', with args "+str(args)+" and kwargs "+str(kwargs))
        if event == "on_message":
            await self.get_guild(args[0].guild.id).get_channel(args[0].channel.id).send("An error occured...")
    '''

if __name__ == "__main__":
    io = IOM("configs.json")

    if io.read() == {}:
        io.write({
            "clientToken": None,
            "ytToken": None,
            "prefix": "!"
        })

    bot = Bot()

    io.stop()
    while not io.isStopped():
        time.sleep(.5)
