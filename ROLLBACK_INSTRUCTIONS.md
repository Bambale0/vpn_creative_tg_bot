# Инструкции по переносу и развертыванию VPN Bot на новом сервере

## Шаг 1: Подготовка нового сервера
1. Установите Docker и docker-compose на новый сервер
2. Установите git (для клонирования репозитория)

## Шаг 2: Копирование бекапа
1. Переместите архив `vpnbot_backup_full.tar.gz` на новый сервер
2. Разархивируйте: `tar -xzf vpnbot_backup_full.tar.gz`

## Шаг 3: Восстановление nginx конфигурации
1. Скопируйте конфигурации из `nginx_backup/` в `/etc/nginx/`:
   - `sudo cp nginx_backup/nginx.conf /etc/nginx/nginx.conf`
   - `sudo cp nginx_backup/vpn.chillcreative.ru /etc/nginx/sites-available/vpn.chillcreative.ru` (если используется)
   - Создайте symbolic link: `sudo ln -s /etc/nginx/sites-available/vpn.chillcreative.ru /etc/nginx/sites-enabled/`
2. Убедитесь, что SSL сертификаты на месте в `/etc/nginx/ssl/`
3. Перезапустите nginx: `sudo systemctl restart nginx`

## Шаг 3.5: Восстановление WireGuard
1. Создайте директорию: `sudo mkdir -p /etc/wireguard`
2. Скопируйте ключи и конфигурации: `sudo cp nginx_backup/wf_backup/privatekey /etc/wireguard/` и аналогично для publickey, wg0.conf, wg0.conf.backup
3. Настройте системный сервис WireGuard: `sudo systemctl enable wg-quick@wg0`
4. Запустите: `sudo systemctl start wg-quick@wg0`

## Шаг 4: Настройка переменных окружения
1. Перейдите в директорию проекта: `cd vpnbot_consolidated`
2. Проверьте и скорректируйте `.env` файл с новыми настройками сервера
3. Убедитесь, что все необходимые секреты (токены, ключи) правильно указаны

## Шаг 5: Восстановление баз данных
1. Скопируйте файлы баз данных из `data/*.db` в соответствующие места
2. Если нужныдампы SQL, они могут быть в `data/*.sql` (если удалось создать)

## Шаг 6: Развертывание
1. Запустите деплои-скрипт: `chmod +x deploy.sh && ./deploy.sh`
2. Соберите и запустите сервисы: `./deploy.sh start`

## Шаг 7: После развертывания
1. Проверьте статус: `./deploy.sh status`
2. Просмотрите логи: `./deploy.sh logs`
3. Убедитесь, что веб-интерфейс и бот работают на новом сервере

## Дополнительные файлы
- SSL сертификаты: `ssl/`
- Логи: `logs/` (можно очистить перед переносом, если не нужны)
- Конфигурации: `config/`

## Примечания
- Убедитесь, что на новом сервере открыт 443 порт для HTTPS
- Настройте брандмауэр (ufw или iptables) для необходимых портов
- Установите сертификаты SSL на новый сервер

## Резервный план
Если что-то пойдет не так, есть гарпированный бекап в `vpnbot_backup_full.tar.gz`
