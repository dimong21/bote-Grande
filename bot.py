import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
from datetime import datetime
import pytz
import json
import os
import time
from dotenv import load_dotenv

load_dotenv()

# ============ КОНФИГ ============
TOKEN = os.getenv("VK_USER_TOKEN")
GROUP_ID = int(os.getenv("VK_GROUP_ID"))
ADMIN_ID = int(os.getenv("ADMIN_ID"))
TZ_OFFSET = int(os.getenv("TIMEZONE_OFFSET", 3))
DATA_DIR = "/app/data"

os.makedirs(DATA_DIR, exist_ok=True)

MSK = pytz.timezone("Europe/Moscow")

# ============ ФАЙЛЫ ДАННЫХ ============
LINKS_FILE = f"{DATA_DIR}/links.json"
ROLES_FILE = f"{DATA_DIR}/roles.json"
PERMS_FILE = f"{DATA_DIR}/perms.json"  # Файл с разрешениями на команды

# ============ РОЛИ (ЗВАНИЯ) ============
ROLES = {
    1: "Куратор обучения",
    2: "Заместитель Руководителя отдела",
    3: "Руководитель отдела",
    4: "Наставник отдела",
    5: "Администрация Grand",
    6: "Куратор отдела"
}

# Все доступные команды (для выдачи прав)
ALL_COMMANDS = [
    "ping", "id", "help",
    "role_info", "role_list", "role_give",
    "access_info", "access_give",
    "links_add", "links_del", "links_list",
    "setprobiv", "requests", "accept",
    "decline", "members", "kick"
]

# ============ ЗАГРУЗКА ДАННЫХ ============
def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

links = load_json(LINKS_FILE, {})
roles = load_json(ROLES_FILE, {})
perms = load_json(PERMS_FILE, {})  # {user_id: ["cmd1", "cmd2"]}

# ============ ВК АВТОРИЗАЦИЯ ============
vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkLongPoll(vk_session)

# ============ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ============
def get_role(user_id: int) -> int:
    return roles.get(str(user_id), 0)

def get_role_name(level: int) -> str:
    return ROLES.get(level, "Нет роли")

def get_user_perms(user_id: int) -> list:
    """Возвращает список команд, доступных пользователю"""
    if user_id == ADMIN_ID:
        return ALL_COMMANDS.copy()
    return perms.get(str(user_id), [])

def has_access(user_id: int, command: str) -> bool:
    """Проверяет, есть ли у пользователя доступ к команде"""
    if user_id == ADMIN_ID:
        return True
    user_perms = perms.get(str(user_id), [])
    return command in user_perms

def send_message(peer_id: int, text: str):
    vk.messages.send(
        peer_id=peer_id,
        message=text,
        random_id=get_random_id()
    )

def get_user_info(user_id: int):
    try:
        resp = vk.users.get(user_ids=[user_id], fields="domain")[0]
        return f"@id{resp['id']} ({resp['first_name']} {resp['last_name']})"
    except:
        return f"id{user_id}"

def parse_id_from_text(text: str):
    text = text.strip()
    if text.isdigit():
        return int(text)
    if "vk.com/" in text:
        screen_name = text.split("vk.com/")[-1].split()[0].strip("/")
        if screen_name.isdigit():
            return int(screen_name)
        try:
            return vk.utils.resolveScreenName(screen_name=screen_name)["object_id"]
        except:
            return None
    if "@id" in text:
        try:
            return int(text.split("@id")[1].split()[0].split("(")[0].split("]")[0])
        except:
            return None
    return None

def access_denied(peer_id):
    send_message(peer_id, "⛔ У вас нет доступа к этой команде")

# ============ КОМАНДЫ ============

# --- Базовые (доступ есть всегда) ---
def cmd_ping(peer_id, user_id):
    start = time.time()
    try:
        vk.users.get(user_ids=[1])
        api_ok = True
    except:
        api_ok = False
    latency = round((time.time() - start) * 1000, 2)
    status = "✅" if api_ok else "❌"
    send_message(peer_id, f"🏓 Понг! {latency} мс\n📡 API: {status}")

def cmd_id(peer_id, user_id, args):
    if args:
        target = parse_id_from_text(args)
        if target:
            info = get_user_info(target)
            send_message(peer_id, f"🔍 {info}\n🆔 ID: {target}")
        else:
            send_message(peer_id, "❌ Не удалось определить ID")
    else:
        info = get_user_info(user_id)
        send_message(peer_id, f"👤 {info}\n🆔 Ваш ID: {user_id}")

def cmd_help(peer_id, user_id):
    user_perms = get_user_perms(user_id)
    msg = f"""📖 **ДОСТУПНЫЕ КОМАНДЫ**
👤 Ваша роль: {get_role_name(get_role(user_id))}
🔑 Доступные команды: {', '.join(user_perms) if user_perms else 'базовые'}

**Базовые команды (доступны всем):**
.ping - Проверка задержки и API
.id [ссылка] - Узнать ID
.help - Это сообщение
.role info [ID] - Информация о роли
.access info [ID] - Список команд пользователя

**Команды по доступу:**
.role list - Список ролей
.role give <ID> <1-6> - Выдать роль
.access give <ID> <команда/список> - Выдать доступ к командам
.access take <ID> <команда/список> - Забрать доступ
.access list - Список всех команд
.links add <ссылка> - Добавить ссылку
.links del <ссылка> - Удалить ссылку
.links list - Список ссылок
.setprobiv - Запустить пробив агентов
.requests - Список заявок
.accept <ID> - Принять заявку
.decline <ID> - Отклонить заявку
.members - Участники сообщества
.kick <ID> - Удалить из сообщества

👑 Администратор имеет доступ ко всем командам"""
    send_message(peer_id, msg)

# --- Управление доступом ---
def cmd_access_give(peer_id, user_id, args):
    parts = args.split(maxsplit=1)
    if len(parts) < 2:
        send_message(peer_id, "⚠️ Использование: .access give <ID> <команда или список через запятую>")
        send_message(peer_id, "Пример: .access give @durov links_add, links_del, setprobiv")
        return

    target_id = parse_id_from_text(parts[0])
    if not target_id:
        send_message(peer_id, "❌ Пользователь не найден")
        return

    # Разбираем список команд
    cmds_raw = parts[1].replace(",", " ").split()
    cmds = []
    invalid = []

    for c in cmds_raw:
        c = c.strip().lower()
        if c in ALL_COMMANDS:
            cmds.append(c)
        elif c == "all":
            cmds = ALL_COMMANDS.copy()
            break
        else:
            invalid.append(c)

    if invalid:
        send_message(peer_id, f"⚠️ Неизвестные команды: {', '.join(invalid)}")
        if not cmds:
            return

    # Выдаём доступ
    target_str = str(target_id)
    if target_str not in perms:
        perms[target_str] = []

    added = []
    for cmd in cmds:
        if cmd not in perms[target_str]:
            perms[target_str].append(cmd)
            added.append(cmd)

    save_json(PERMS_FILE, perms)

    if added:
        send_message(peer_id, f"✅ {get_user_info(target_id)} получил доступ к командам: {', '.join(added)}")
    else:
        send_message(peer_id, "ℹ️ У пользователя уже есть доступ ко всем указанным командам")

def cmd_access_take(peer_id, user_id, args):
    parts = args.split(maxsplit=1)
    if len(parts) < 2:
        send_message(peer_id, "⚠️ Использование: .access take <ID> <команда или список через запятую>")
        return

    target_id = parse_id_from_text(parts[0])
    if not target_id:
        send_message(peer_id, "❌ Пользователь не найден")
        return

    cmds_raw = parts[1].replace(",", " ").split()
    cmds = [c.strip().lower() for c in cmds_raw if c.strip().lower() in ALL_COMMANDS]

    if "all" in cmds_raw:
        perms[str(target_id)] = []
        save_json(PERMS_FILE, perms)
        send_message(peer_id, f"✅ У {get_user_info(target_id)} забраны все права")
        return

    target_str = str(target_id)
    if target_str in perms:
        removed = []
        for cmd in cmds:
            if cmd in perms[target_str]:
                perms[target_str].remove(cmd)
                removed.append(cmd)
        save_json(PERMS_FILE, perms)
        if removed:
            send_message(peer_id, f"✅ У {get_user_info(target_id)} забран доступ к командам: {', '.join(removed)}")
        else:
            send_message(peer_id, "ℹ️ У пользователя и так нет доступа к этим командам")
    else:
        send_message(peer_id, "ℹ️ У пользователя нет никаких прав")

def cmd_access_list(peer_id, user_id):
    msg = "📋 **Список всех команд:**\n"
    for i, cmd in enumerate(ALL_COMMANDS, 1):
        msg += f"{i}. {cmd}\n"
    msg += "\n💡 Используйте 'all' чтобы выдать все команды сразу"
    send_message(peer_id, msg)

def cmd_access_info(peer_id, user_id, args):
    if args:
        target_id = parse_id_from_text(args)
    else:
        target_id = user_id

    if not target_id:
        send_message(peer_id, "❌ Пользователь не найден")
        return

    user_perms = get_user_perms(target_id)
    if user_perms:
        msg = f"👤 {get_user_info(target_id)}\n🔑 Команды: {', '.join(user_perms)}"
    else:
        msg = f"👤 {get_user_info(target_id)}\n🔑 Только базовые команды"
    send_message(peer_id, msg)

# --- Роли ---
def cmd_role_list(peer_id, user_id):
    msg = "📋 **Список ролей:**\n"
    for lvl, name in ROLES.items():
        msg += f"{lvl}. {name}\n"
    send_message(peer_id, msg)

def cmd_role_give(peer_id, user_id, args):
    parts = args.split()
    if len(parts) < 2:
        send_message(peer_id, "⚠️ Использование: .role give <ID> <уровень 1-6>")
        return

    target_id = parse_id_from_text(parts[0])
    if not target_id:
        send_message(peer_id, "❌ Пользователь не найден")
        return

    try:
        level = int(parts[1])
        if level not in ROLES:
            send_message(peer_id, "❌ Уровень должен быть от 1 до 6")
            return
    except:
        send_message(peer_id, "❌ Уровень должен быть числом")
        return

    roles[str(target_id)] = level
    save_json(ROLES_FILE, roles)
    send_message(peer_id, f"✅ {get_user_info(target_id)} получил роль: {ROLES[level]}")

def cmd_role_info(peer_id, user_id, args):
    if args:
        target_id = parse_id_from_text(args)
    else:
        target_id = user_id

    if not target_id:
        send_message(peer_id, "❌ Пользователь не найден")
        return

    level = get_role(target_id)
    send_message(peer_id, f"👤 {get_user_info(target_id)}\n📌 Роль: {get_role_name(level)}")

# --- Ссылки ---
def cmd_links_list(peer_id, user_id):
    chat_id = str(peer_id)
    lst = links.get(chat_id, [])
    if not lst:
        send_message(peer_id, "📭 Список ссылок пуст")
    else:
        msg = "🔗 **Ссылки для пробива:**\n" + "\n".join(f"• {l}" for l in lst)
        send_message(peer_id, msg)

def cmd_links_add(peer_id, user_id, args):
    if not args:
        send_message(peer_id, "⚠️ Укажите ссылку: .links add <ссылка>")
        return

    chat_id = str(peer_id)
    if chat_id not in links:
        links[chat_id] = []

    if args in links[chat_id]:
        send_message(peer_id, "⚠️ Ссылка уже в списке")
        return

    links[chat_id].append(args)
    save_json(LINKS_FILE, links)
    send_message(peer_id, f"✅ Ссылка добавлена")

def cmd_links_del(peer_id, user_id, args):
    if not args:
        send_message(peer_id, "⚠️ Укажите ссылку: .links del <ссылка>")
        return

    chat_id = str(peer_id)
    if chat_id in links and args in links[chat_id]:
        links[chat_id].remove(args)
        save_json(LINKS_FILE, links)
        send_message(peer_id, "✅ Ссылка удалена")
    else:
        send_message(peer_id, "❌ Ссылка не найдена")

# --- Пробив ---
def cmd_setprobiv(peer_id, user_id):
    chat_id = str(peer_id)
    lst = links.get(chat_id, [])
    if not lst:
        send_message(peer_id, "📭 Нет ссылок для пробива")
        return

    now = datetime.now(MSK)
    msg = f"🕵️ **ПРОБИВ АГЕНТОВ**\n⏰ {now.strftime('%d.%m.%Y %H:%M:%S')} МСК\n\n"
    msg += "🔗 Пробиваемые ссылки:\n" + "\n".join(lst)
    send_message(peer_id, msg)

# --- Управление сообществом ---
def cmd_requests(peer_id, user_id):
    try:
        resp = vk.groups.getRequests(group_id=GROUP_ID, count=200)
        count = resp["count"]
        items = resp["items"]
        if count == 0:
            send_message(peer_id, "📭 Нет заявок на вступление")
            return
        msg = f"📋 **Заявки на вступление** ({count}):\n"
        for i, uid in enumerate(items[:30], 1):
            info = get_user_info(uid)
            msg += f"{i}. {info}\n"
        if count > 30:
            msg += f"\n... и ещё {count - 30} заявок"
        send_message(peer_id, msg)
    except Exception as e:
        send_message(peer_id, f"❌ Ошибка: {e}")

def cmd_members(peer_id, user_id):
    try:
        resp = vk.groups.getMembers(group_id=GROUP_ID, fields="domain", count=1000)
        count = resp["count"]
        members = resp["items"]
        msg = f"👥 **Участники сообщества** ({count}):\n"
        for i, m in enumerate(members[:30], 1):
            msg += f"{i}. @id{m['id']} ({m['first_name']} {m['last_name']})\n"
        if count > 30:
            msg += f"\n... и ещё {count - 30} участников"
        send_message(peer_id, msg)
    except Exception as e:
        send_message(peer_id, f"❌ Ошибка: {e}")

def cmd_accept(peer_id, user_id, args):
    if not args:
        send_message(peer_id, "⚠️ Укажите ID или ссылку пользователя")
        return

    target_id = parse_id_from_text(args)
    if not target_id:
        send_message(peer_id, "❌ Пользователь не найден")
        return

    try:
        vk.groups.approveRequest(group_id=GROUP_ID, user_id=target_id)
        send_message(peer_id, f"✅ Заявка от {get_user_info(target_id)} принята")
    except Exception as e:
        send_message(peer_id, f"❌ Ошибка: {e}")

def cmd_decline(peer_id, user_id, args):
    if not args:
        send_message(peer_id, "⚠️ Укажите ID или ссылку пользователя")
        return

    target_id = parse_id_from_text(args)
    if not target_id:
        send_message(peer_id, "❌ Пользователь не найден")
        return

    try:
        vk.groups.removeUser(group_id=GROUP_ID, user_id=target_id)
        send_message(peer_id, f"❌ Заявка отклонена / пользователь удалён")
    except Exception as e:
        send_message(peer_id, f"❌ Ошибка: {e}")

def cmd_kick(peer_id, user_id, args):
    if not args:
        send_message(peer_id, "⚠️ Укажите ID или ссылку пользователя")
        return

    target_id = parse_id_from_text(args)
    if not target_id:
        send_message(peer_id, "❌ Пользователь не найден")
        return

    try:
        vk.groups.removeUser(group_id=GROUP_ID, user_id=target_id)
        send_message(peer_id, f"🚫 Пользователь удалён из сообщества")
    except Exception as e:
        send_message(peer_id, f"❌ Ошибка: {e}")

# ============ ОБРАБОТЧИК КОМАНД ============
COMMANDS = {
    # Базовые (без проверки прав)
    ".ping": (cmd_ping, False),
    ".id": (cmd_id, False),
    ".help": (cmd_help, False),
    ".role info": (cmd_role_info, False),
    ".access info": (cmd_access_info, False),

    # Требуют проверки прав
    ".access give": (cmd_access_give, "access_give"),
    ".access take": (cmd_access_take, "access_take"),
    ".access list": (cmd_access_list, "access_list"),
    ".role list": (cmd_role_list, "role_list"),
    ".role give": (cmd_role_give, "role_give"),
    ".links add": (cmd_links_add, "links_add"),
    ".links del": (cmd_links_del, "links_del"),
    ".links list": (cmd_links_list, "links_list"),
    ".setprobiv": (cmd_setprobiv, "setprobiv"),
    ".requests": (cmd_requests, "requests"),
    ".members": (cmd_members, "members"),
    ".accept": (cmd_accept, "accept"),
    ".decline": (cmd_decline, "decline"),
    ".kick": (cmd_kick, "kick"),
}

print("🤖 Бот ЕЛП запущен...")

for event in longpoll.listen():
    if event.type == VkEventType.MESSAGE_NEW and event.to_me and event.text:
        text = event.text.strip()
        peer_id = event.peer_id
        user_id = event.user_id

        if not text.startswith("."):
            continue

        handled = False
        for cmd_prefix, (handler, required_perm) in COMMANDS.items():
            if text.lower().startswith(cmd_prefix):
                args = text[len(cmd_prefix):].strip()

                if required_perm is False or has_access(user_id, required_perm):
                    handler(peer_id, user_id, args)
                else:
                    access_denied(peer_id)

                handled = True
                break

        if not handled:
            send_message(peer_id, "❓ Неизвестная команда. Введите .help для списка команд")
