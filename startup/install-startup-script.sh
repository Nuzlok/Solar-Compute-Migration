
sudo apt install -y python3-systemd
sudp cp ./migrator-service.service /etc/systemd/system/migrator-service.service
sudo systemctl daemon-reload
sudo systemctl enable migrator-service.service
sleep 5
sudo systemctl status migrator-service.service
# sudo journalctl -u myprogram.service
