import discord
import asyncio
import time

from iomanage import IOManager as IOM

class Bot(discord.Client):

    ## Command functions

    async def tst_cmd(self, msg, parts):
        await msg.channel.send(msg.author.mention+", bot is recieving commands.")

    async def hlp_cmd(self, msg, parts):

        # Is the user asking for help for a specific command?
        if len(parts) == 2: # Yes
            cmd = self.SearchCommand(parts[1])
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

    ## Utility funcs

    def __init__(self):
        super().__init__()

        self.Commands = []
        self.Newbies = []

        ## Commands

        self.CreateCommand(
            "test",
            self.tst_cmd,
            "Test to see if bot is recieving commands.",
            roles = [
                632518235987902485
            ]
        )

        self.CreateCommand(
            "help",
            self.hlp_cmd,
            "List commands and their descriptions, or use {}help <command> to describe a specific command.".format(io.Read()['prefix'])
        )

        self.CreateCommand(
            "check",
            self.priv_check_cmd,
            "Check if you are compliant with servers privacy policy, and assign role accordingly."
        )

        self.run(io.Read()['clientToken'])

    # Search for command, returns command dict
    def SearchCommand(self, name):
        name = name.lower()
        for command in self.Commands:
            if command['name'] == name or name in command['alias']:
                return command
        return None

    # Create a command
    def CreateCommand(self, name, function, description, roles=[], alias=[], asyncio=True):
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
        if not self.SearchCommand(name) == None:
            isNew = False
            taken.append(name)
        for a in alias:
            if not self.SearchCommand(a) == None:
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
                if payload.emoji.id == 476801025991507979:
                    print("[USR] Obtained gender role 'everything'")
                    await self.give_member_role(payload.user_id, 632522554074071050)
                if payload.emoji.id == 527053057171783690:
                    print("[USR] Obtained gender role 'nothing'")
                    await self.give_member_role(payload.user_id, 632524877412171788)
                if payload.emoji.id == 590028360772616193:
                    print("[USR] Obtained gender role 'female'")
                    await self.give_member_role(payload.user_id, 632522281888776202)
            elif payload.message_id == 632528504319377449:
                if payload.emoji.id == 556161748822917120:
                    print("[USR] Obtained age role '18+'")
                    await self.give_member_role(payload.user_id, 632525773756170260)
                if payload.emoji.id == 533032578165506058:
                    print("[USR] Obtained age role '<18'")
                    await self.give_member_role(payload.user_id, 632516288111050752)


    async def on_raw_reaction_remove(self, payload):
        if payload.guild_id == 632460050660720650:
            if payload.message_id == 632527260859236373:
                if payload.emoji.id == 590028329277718538:
                    print("[USR] Removed gender role 'male'")
                    await self.remove_member_role(payload.user_id, 632522224024289301)
                if payload.emoji.id == 476801025991507979:
                    print("[USR] Removed gender role 'everything'")
                    await self.remove_member_role(payload.user_id, 632522554074071050)
                if payload.emoji.id == 527053057171783690:
                    print("[USR] Removed gender role 'nothing'")
                    await self.remove_member_role(payload.user_id, 632524877412171788)
                if payload.emoji.id == 590028360772616193:
                    print("[USR] Removed gender role 'female'")
                    await self.remove_member_role(payload.user_id, 632522281888776202)
            elif payload.message_id == 632528504319377449:
                if payload.emoji.id == 556161748822917120:
                    print("[USR] Removed age role '18+'")
                    await self.remove_member_role(payload.user_id, 632525773756170260)
                if payload.emoji.id == 533032578165506058:
                    print("[USR] Removed age role '<18'")
                    await self.remove_member_role(payload.user_id, 632516288111050752)


    async def on_message(self, msg):
        if not msg.author.bot:
            if msg.channel.guild.id == 632460050660720650:
                pf = io.Read()['prefix']
                if msg.content.startswith(pf):
                    parts = msg.content[len(pf):].split(" ")
                    command = self.SearchCommand(parts[0])
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
        await asyncio.ensure_future(self.priv_check_loop())

if __name__ == "__main__":
    io = IOM("configs.json")

    if io.Read() == {}:
        io.Write({
            "clientToken": None,
            "prefix": "!"
        })

    bot = Bot()

    io.Stop()
    while not io.isStopped():
        time.sleep(.5)
