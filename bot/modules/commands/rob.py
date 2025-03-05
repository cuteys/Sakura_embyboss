import asyncio
import random
import sys
from asyncio import Lock

from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot import bot, prefixes
from bot.func_helper.msg_utils import deleteMessage, editMessage
from bot.sql_helper.sql_emby import sql_get_emby, sql_update_emby, Emby

# COMMISSION_FEE = 50     # 对决佣金
# MAX_COMMISSION_FEE = sys.maxsize  # 最大对决钱
ROB_TIME = 10  # 对决持续时间
rob_games = {}
# 添加全局锁字典
rob_locks = {}


def get_lock(key):
    if key not in rob_locks:
        rob_locks[key] = Lock()
    return rob_locks[key]


async def delete_msg_with_error(msg, error_text):
    error_message = await bot.send_message(msg.chat.id, error_text, reply_to_message_id=msg.id)
    asyncio.create_task(deleteMessage(error_message, 30))
    asyncio.create_task(deleteMessage(msg, 30))


def change_emby_amount(user_id, amount):
    sql_update_emby(Emby.tg == user_id, iv=amount)


async def countdown(call, rob_message):
    while True:
        await asyncio.sleep(60)
        if rob_message.id in rob_games:
            game = rob_games[rob_message.id]
            game['remaining_time'] -= 1
            await update_edit_message(call, game)


async def start_rob(message, user, target_user):
    # Send the narrative message first
    narrative_msg = await bot.send_message(
        message.chat.id,
        f"1899年，枪手和亡命之徒的时代已然走到尽头，美国逐渐成为了一个法治的国度……连西部都几乎被彻底征服。\n只有少数帮派仍在逍遥法外，但他们难逃被追捕的命运，终将不复存在。\n\n事件系统正在初始化...",
        reply_to_message_id=message.id
    )

    # Wait 5 seconds
    await asyncio.sleep(5)

    # Delete the narrative message
    await deleteMessage(narrative_msg)

    global rob_games

    rob_amount = user.iv + target_user.iv
    # rob_amount = random.randint(COMMISSION_FEE, MAX_COMMISSION_FEE)
    user_with_link = await get_fullname_with_link(user.tg)
    target_with_link = await get_fullname_with_link(target_user.tg)
    keyboard_rob = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                text='💸 破财消灾',
                callback_data=f'rob_flee_{rob_amount}_{user.tg}_{target_user.tg}'
            ),
            InlineKeyboardButton(
                text='⚔️ We shall never surrender!',
                callback_data=f'rob_fight_{rob_amount}_{user.tg}_{target_user.tg}'
            )
        ],
        [
            InlineKeyboardButton(
                text='📺 看客',
                callback_data=f'rob_watch_{rob_amount}_{user.tg}_{target_user.tg}'
            )
        ]
    ])

    rob_prepare_text = (
        f"· [西部最强]\n\n"
        f"· 🥷 委托雇主 | {user_with_link}\n"
        f"· ⚔️ 决战对象 | {target_with_link}\n"
        f"· 💵 决战分红 | {rob_amount}\n"
        f"· ⏳ 剩余时间 | 10 分钟\n"
        f"· 🔥 战斗回合 | ROUND 0\n\n"
        f"· 西部最强 : 等待投点\n"
        f"· VS\n"
        f"· {target_with_link} : 等待投点\n\n"
        f"· 🤑 看客:\n"
    )
    rob_message = await bot.send_message(
        message.chat.id,
        rob_prepare_text,
        reply_to_message_id=message.id,
        reply_markup=keyboard_rob
    )
    rob_games[rob_message.id] = {
        "target_user_id": target_user.tg,
        "user_id": user.tg,
        "rob_gold": rob_amount,
        "rob_prepare_text": rob_prepare_text,
        "watch_list": [],
        "round_time": 0,
        "user_score": 0,
        "target_score": 0,
        "watch_name": "",
        "rob_msg_id": rob_message.id,
        "original_message": rob_message,
        "remaining_time": ROB_TIME,  # 剩余时间，单位：分钟
        "chat_id": message.chat.id  # 群聊ID
    }

    asyncio.create_task(countdown(message, rob_message))


async def show_onlooker_message(call, game):
    onlookers_messages = ["· 📺 看客"]
    if game['watch_list']:
        for watch_id in game['watch_list']:
            name = await get_fullname_with_link(watch_id)
            possible_messages = [
                f"· {name} 纷纷说道：这都啥……",
                f"· {name} 纷纷说道：板凳都搬来了……",
                f"· {name} 纷纷说道：就给我看这些……"
            ]
            # 随机选择一条消息
            selected_message = random.choice(possible_messages)
            # 追加选中的消息
            onlookers_messages.append(selected_message)

    reward_message = "\n".join(onlookers_messages)

    reward_msg = await bot.send_message(game['chat_id'], reward_message, reply_to_message_id=game['rob_msg_id'])

    asyncio.create_task(deleteMessage(reward_msg, 180))


async def update_edit_message(call, game, status=None):
    user_with_link = await get_fullname_with_link(game['user_id'])
    target_with_link = await get_fullname_with_link(game['target_user_id'])
    user_score = '等待投点' if game['round_time'] == 0 else str(game['user_score']) + ' 分'
    target_score = '等待投点' if game['round_time'] == 0 else str(game['target_score']) + ' 分'
    update_text = (
        f"· [西部最强]\n\n"
        f"· 🥷 委托雇主 | {user_with_link}\n"
        f"· ⚔️ 决战对象 | {target_with_link}\n"
        f"· 💵 决战分红 | {game['rob_gold']}\n"
        f"· ⏳ 剩余时间 | {game['remaining_time']} 分钟\n"
        f"· 🔥 战斗回合 | ROUND {game['round_time']}\n\n"
        f"· 乱世的盗贼 : {user_score}\n"
        f"· VS\n"
        f"· {target_with_link} : {target_score}\n\n"
    )

    if status == 'surrender':
        update_text += f"· 🎫 最终结果 | {user_with_link} 获胜！\n"
        user = sql_get_emby(game['user_id'])
        target_user = sql_get_emby(game['target_user_id'])
        if target_user.iv < game['rob_gold']:
            # rob_gold = random.randint(25, target_user.iv)
            rob_gold = target_user.iv
        else:
            # rob_gold = random.randint(50, game['rob_gold'])
            rob_gold = game['rob_gold']
        change_emby_amount(game['user_id'], user.iv + rob_gold)
        change_emby_amount(game['target_user_id'], target_user.iv - rob_gold)

        await editMessage(game['original_message'], update_text)
        answer = f"对方投降了，你获得 **{rob_gold}** Coin， 剩余 {user.iv + rob_gold} Coin✌️！\n"

        await bot.send_message(user.tg, answer, reply_to_message_id=call.message.id)

        target_answer = f"你投降了，割地赔款 **{rob_gold}** Coin， 剩余 {target_user.iv - rob_gold} Coin️！\n"
        await bot.send_message(target_user.tg, target_answer, reply_to_message_id=call.message.id)

        del rob_games[game['rob_msg_id']]
        return

    if game['remaining_time'] <= 0:
        buttons = []
        target_score = random.randint(0, 10)
        user_score = random.randint(0, 10)
        user = sql_get_emby(game['user_id'])
        target_user = sql_get_emby(game['target_user_id'])
        if target_score < user_score:
            update_text += f"· 🎫 最终结果 | {user_with_link} 获胜！\n"
            if target_user.iv >= game['rob_gold']:
                change_emby_amount(game['user_id'], user.iv + game['rob_gold'])
                change_emby_amount(game['target_user_id'], target_user.iv - game['rob_gold'])
            else:
                partial_gold = target_user.iv
                change_emby_amount(game['user_id'], user.iv + partial_gold)
                change_emby_amount(game['target_user_id'], 0)
            await editMessage(game['original_message'], update_text, buttons)
            not_answer = f"{target_with_link} 没有反应，{user_with_link} 顺利抢走 **{game['rob_gold']}** Coin✌️！\n"
            no_answer_msg = await bot.send_message(call.chat.id, not_answer, reply_to_message_id=call.id)
        else:
            update_text += f"· 🎫 最终结果 | {target_with_link} 获胜！\n"
            if user.iv < game['rob_gold']:
                compensation = user.iv
            else:
                compensation = game['rob_gold']
            # compensation = random.randint(1, 50) if user.iv > 50 else random.randint(1, user.iv)
            change_emby_amount(game['user_id'], user.iv - compensation)
            change_emby_amount(game['target_user_id'], target_user.iv + compensation)
            await editMessage(game['original_message'], update_text, buttons)
            not_answer = f"{target_with_link} 邻居发现了{user_with_link} 在抢劫并报警吓跑了他，获得 **{compensation}** Coin作为补偿✌️！\n"
            no_answer_msg = await bot.send_message(call.chat.id, not_answer, reply_to_message_id=call.id)

        await show_onlooker_message(call, game)

        asyncio.create_task(deleteMessage(game['original_message'], 180))
        asyncio.create_task(deleteMessage(no_answer_msg, 180))
        del rob_games[game['rob_msg_id']]
    else:
        if game['round_time'] < 3:
            buttons = get_buttons(game)
            update_text += f"· 📺看客:\n {game['watch_name']}"
            await editMessage(game['original_message'], update_text, buttons)
        else:
            await editMessage(game['original_message'], update_text)
            # await show_onlooker_message(call, game)
            # del rob_games[game['rob_msg_id']]


def get_buttons(game):
    flee_button = InlineKeyboardButton(
        text='💸 破财消灾',
        callback_data=f'rob_flee_{game["rob_gold"]}_{game["user_id"]}_{game["target_user_id"]}'
    )
    fight_button = InlineKeyboardButton(
        text='⚔️ We shall never surrender!',
        callback_data=f'rob_fight_{game["rob_gold"]}_{game["user_id"]}_{game["target_user_id"]}')
    watch_button = InlineKeyboardButton(
        text='📺 看客',
        callback_data=f'rob_watch_{game["rob_gold"]}_{game["user_id"]}_{game["target_user_id"]}')
    return InlineKeyboardMarkup([[flee_button, fight_button], [watch_button]])


async def onlookers(call):
    # 看客
    game = rob_games[call.message.id]
    if call.from_user.id != int(call.data.split("_")[4]):
        watch_id = call.from_user.id
        if watch_id not in game['watch_list']:
            game['watch_list'].append(watch_id)
            name_ = await get_fullname_with_link(watch_id)
            game['watch_name'] += f". {name_} 看戏中…\n"
            await update_edit_message(call, game)
        else:
            await call.answer("您已经在看戏了！", show_alert=False)
    else:
        await call.answer("您已经被盯上了！", show_alert=False)


async def surrender(call, game_id):
    # 投降
    game = rob_games.get(game_id)
    if game is None:
        await call.answer("这个对决已经无效。", show_alert=True)
        return

    if call.from_user.id == int(call.data.split("_")[4]):
        target_with_link = await get_fullname_with_link(int(call.data.split("_")[4]))
        user_with_link = await get_fullname_with_link(int(call.data.split("_")[3]))
        # 发送新消息，表示抢劫结果
        result_text = f"{user_with_link} 不花一兵一卒拿下🏆\n{target_with_link} 居然直接给钱懦夫😭"
        result_msg = await bot.send_message(call.message.chat.id, result_text, reply_to_message_id=call.message.id)
        asyncio.create_task(deleteMessage(result_msg, 180))
        await update_edit_message(call, game, 'surrender')
        # del rob_games[game_id]
    else:
        await call.answer("您只是看客！", show_alert=False)


async def fighting(call, game_id):
    # 战斗
    game = rob_games.get(game_id)
    if game is None:
        await call.answer("这个对决已经无效。", show_alert=True)
        return

    if call.from_user.id == int(call.data.split("_")[4]):
        # 开始决斗
        if game["round_time"] < 3:
            game["round_time"] += 1
            game["user_score"] += random.randint(0, 6)
            game['target_score'] += random.randint(0, 6)

            target_with_link = await get_fullname_with_link(int(call.data.split("_")[4]))
            user_with_link = await get_fullname_with_link(int(call.data.split("_")[3]))
            await update_edit_message(call, game)
            if game["round_time"] >= 3:
                user = sql_get_emby(int(call.data.split("_")[3]))
                target_user = sql_get_emby(int(call.data.split("_")[4]))

                if game["target_score"] > game["user_score"]:
                    msg = f"{target_with_link} 最终赢得了斗争🏆\n{user_with_link} 失去 {COMMISSION_FEE} Coin😭"
                    success_msg = await bot.send_message(call.message.chat.id, msg, reply_to_message_id=call.message.id)
                    asyncio.create_task(deleteMessage(success_msg, 180))
                    change_emby_amount(call.from_user.id, target_user.iv + COMMISSION_FEE)
                    # 给对决者私发消息
                    await bot.send_message(
                        user.tg,
                        f"乱世的盗贼抢劫失败损失了 {COMMISSION_FEE} Coin，剩余 {sql_get_emby(user.tg).iv} Coin！",
                        reply_to_message_id=call.message.id)
                    # 给被对决者私发消息
                    await bot.send_message(
                        target_user.tg,
                        f"你打赢了乱世的盗贼赢得了 {COMMISSION_FEE} Coin佣金，剩余 {sql_get_emby(target_user.tg).iv} Coin！",
                        reply_to_message_id=call.message.id)
                elif game["target_score"] < game["user_score"]:
                    if target_user.iv < game['rob_gold']:
                        rob_gold = target_user.iv
                        msg = f"{target_with_link} 是个穷鬼全被抢走了🤡\n{user_with_link} 穷鬼也不放过抢走 {rob_gold} Coin🏆"
                        await bot.send_message(
                            user.tg,
                            f"乱世的盗贼帮您抢了 {rob_gold} Coin，剩余 {user.iv + rob_gold} Coin！",
                            reply_to_message_id=call.message.id
                        )
                        await bot.send_message(
                            target_user.tg,
                            f"你未打赢乱世的盗贼损失了 {rob_gold} Coin，剩余 0 Coin！",
                            reply_to_message_id=call.message.id
                        )
                    else:
                        rob_gold = game['rob_gold']
                        msg = f"{target_with_link} 最终反抗失败🤡\n{user_with_link} 抢走 {game['rob_gold']} Coin🏆"

                    change_emby_amount(user.tg, user.iv + rob_gold)
                    change_emby_amount(target_user.tg, target_user.iv - rob_gold)

                    rob_msg = await bot.send_message(call.message.chat.id, msg, reply_to_message_id=call.message.id)
                    asyncio.create_task(deleteMessage(rob_msg, 180))
                else:
                    msg = f"双方竟然打平了, {user_with_link}痛失{COMMISSION_FEE}Coin，什么也没有得到"
                    rob_msg = await bot.send_message(call.message.chat.id, msg, reply_to_message_id=call.message.id)
                    asyncio.create_task(deleteMessage(rob_msg, 180))
                asyncio.create_task(handle_watch_rewards(game))
                asyncio.create_task(deleteMessage(call.message, 180))
                del rob_games[game_id]
    else:
        await call.answer("您只是看客！", show_alert=False)


async def handle_watch_rewards(rob_game):
    # 定义常量
    TOTAL_GAME_COINS = 30  # 总分不能超过30分
    PENALTY_CHANCE = 25  # 25% 几率扣分
    BONUS_CHANCE = 25  # 25% 几率得分
    PENALTY_AMOUNT = 5  # 扣分数量
    BONUS_MIN_AMOUNT = 1  # 最小得分数量
    BONUS_MAX_AMOUNT = 5  # 最大得分数量
    LUCKY_AMOUNT = 10  # 幸运大奖金额

    watch_list = rob_game['watch_list']
    total_rewards = 0  # 跟踪总奖励的游戏币数

    luck_number = random.randint(10000, sys.maxsize)

    if watch_list:
        reward_messages = []
        tasks = []  # 用于存储并发任务

        for watch_id in watch_list:
            name = await get_fullname_with_link(watch_id)
            watch_user = sql_get_emby(watch_id)
            if watch_id == luck_number:
                change_emby_amount(watch_id, watch_user.iv + LUCKY_AMOUNT)
                reward_messages.append(f". 恭喜 {name} 获得超级幸运大奖， 奖金 {LUCKY_AMOUNT} Coin 🥳")
            else:
                reward_chance = random.randint(1, 100)
                if reward_chance <= PENALTY_CHANCE:  # 被误伤扣分
                    change_emby_amount(watch_id, watch_user.iv - PENALTY_AMOUNT)
                    remaining_gold = sql_get_emby(watch_id).iv
                    reward_messages.append(f"· {name} 被乱世的盗贼误伤，被抢走了 {PENALTY_AMOUNT} Coin🤕")
                    tasks.append(bot.send_message(watch_id, f"您被误伤，损失了 {PENALTY_AMOUNT} Coin😭，剩余 {remaining_gold} Coin"))
                elif reward_chance <= PENALTY_CHANCE + BONUS_CHANCE:  # 捡到Coin
                    bonus_amount = random.randint(BONUS_MIN_AMOUNT, BONUS_MAX_AMOUNT)
                    if total_rewards + bonus_amount > TOTAL_GAME_COINS:
                        bonus_amount = TOTAL_GAME_COINS - total_rewards
                    if bonus_amount > 0:
                        change_emby_amount(watch_id, watch_user.iv + bonus_amount)
                        total_rewards += bonus_amount
                        remaining_gold = sql_get_emby(watch_id).iv
                        reward_messages.append(f"· {name} 在混乱中捡到了 {bonus_amount} Coin，爽🥳")
                        tasks.append(bot.send_message(watch_id, f"您捡到了 {bonus_amount} Coin🍉，剩余 {remaining_gold} Coin"))
                else:  # 什么也没捞到
                    remaining_gold = sql_get_emby(watch_id).iv
                    reward_messages.append(f"· {name} 光顾着吃瓜了，啥也没捞到😕")
                    tasks.append(bot.send_message(watch_id, f"您什么也没捞到😕，剩余 {remaining_gold} Coin"))

        # 等待所有消息发送完成
        if tasks:
            await asyncio.gather(*tasks)

        reward_message = "· 📺 看客\n" + "\n".join(reward_messages)
        result = await bot.send_message(rob_game['chat_id'], reward_message,
                                        reply_to_message_id=rob_game["original_message"].id)

        # 并发删除消息
        asyncio.create_task(deleteMessage(result, 180))


@bot.on_callback_query(filters.regex(r"rob_"))
async def handle_rob_callback(client, call):
    game_id = call.message.id
    lock = get_lock(game_id)

    async with lock:
        try:
            parts = call.data.split('_')

            if not sql_get_emby(call.from_user.id):
                await call.answer("您还未注册Emby账户！", show_alert=True)
                return

            if len(parts) < 5:
                await call.answer("无效的回调数据。", show_alert=True)
                return

            if game_id not in rob_games:
                await call.answer("这个对决已经无效。", show_alert=True)
                return

            if parts[1] == 'watch':
                # 看客看戏
                await onlookers(call)
            elif parts[1] == 'flee':
                # 投降
                await surrender(call, game_id)
            elif parts[1] == 'fight':
                # 战斗
                await fighting(call, game_id)
        except Exception as e:
            # 打印异常信息，以便调试
            print(f"Error handling callback: {e}")
            await call.answer("处理请求时出错。", show_alert=True)
        finally:
            # 此处不需要手动释放锁，async with 语句会自动处理锁的释放
            pass


@bot.on_message(filters.command('rob', prefixes=prefixes) & filters.group)
async def rob_user(_, msg):
    user = sql_get_emby(msg.from_user.id)
    global COMMISSION_FEE
    COMMISSION_FEE = user.iv

    if not msg.reply_to_message:
        if len(msg.command) != 2:
            asyncio.create_task(delete_msg_with_error(msg, "请使用正确的格式：/rob [目标用户ID] 或回复某人的消息使用 /rob"))
            return

    if not user.embyid:
        asyncio.create_task(delete_msg_with_error(msg, '您还未注册Emby账户'))
        return

    target_user = sql_get_emby(msg.reply_to_message.from_user.id)
    if not target_user:
        asyncio.create_task(delete_msg_with_error(msg, '目标用户未注册Emby账户!'))
        return

    if msg.from_user.id == msg.reply_to_message.from_user.id:
        asyncio.create_task(delete_msg_with_error(msg, "目标不能相同"))
        return

    for item in rob_games.values():
        if item['target_user_id'] == target_user.tg:
            asyncio.create_task(delete_msg_with_error(msg, '乱世的盗贼外出了，请稍后再雇佣!'))
            return

    # if target_user.iv <= 50:
    #     asyncio.create_task(delete_msg_with_error(msg, '对方是个穷鬼， 无法对决！'))
    #     return

    if user.iv < COMMISSION_FEE:
        asyncio.create_task(delete_msg_with_error(msg, '您的Coin不足以支付委托费用'))
        return

    change_emby_amount(user.tg, user.iv - COMMISSION_FEE)
    user_with_link = await get_fullname_with_link(user.tg)
    target_with_link = await get_fullname_with_link(target_user.tg)
    message = await bot.send_message(
        msg.chat.id,
        f"接受 { user_with_link } 的委托\n委托费 {COMMISSION_FEE} 对决 {target_with_link}",
        reply_to_message_id=msg.id
    )
    asyncio.create_task(deleteMessage(message, 30))

    await bot.send_message(
        user.tg,
        f"您雇佣了乱世的盗贼花费 {COMMISSION_FEE} Coin，剩余 {sql_get_emby(user.tg).iv} Coin！",
        reply_to_message_id=message.id
    )

    await start_rob(message, user, target_user)
    asyncio.create_task(deleteMessage(msg, 180))


async def get_fullname_with_link(user_id):
    tg_info = await bot.get_users(user_id)
    return f"[{tg_info.first_name}](tg://user?id={tg_info.id})"
