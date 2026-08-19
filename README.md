# Telegram Birthday Reminder Bot

Telegram-бот для хранения дней рождения и ежедневной отправки напоминаний.

## Telegram Mini App

В проект добавлен web-интерфейс для управления контактами. Он запускается отдельным Compose-профилем и не влияет на обычный запуск бота.

### Подготовка

1. Создайте DNS A/AAAA-запись домена на адрес ВМ.
2. Откройте входящие TCP-порты 80 и 443.
3. Добавьте в `.env`:

```dotenv
WEB_DOMAIN=birthdays.example.com
WEB_APP_URL=https://birthdays.example.com
MINI_APP_AUTH_MAX_AGE=86400
```

4. В BotFather настройте Mini App URL равным `WEB_APP_URL`.
5. Убедитесь, что каталог `data` доступен UID/GID 10001:

```bash
sudo chown -R 10001:10001 ./data
```

### Запуск

```bash
docker compose --profile web up -d --build
docker compose ps
docker compose logs --tail=100 reminder_bot web caddy
```

Без профиля `web` запускается только Telegram-бот:

```bash
docker compose up -d --build
```
