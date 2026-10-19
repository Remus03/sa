# Setup iMX95
1. Instalati minicom pentru a avea o interfata cu placa de dezvoltare.
```bash
sudo apt install minicon
```

2. Alimentati placa si conectati prin usb calculatorul. Ghidul placii poate fi accesat [aici].

3. Deschideti o conexiune prin terminal.
```bash
sudo minicom /dev/ttyACM0
```

4. Asteptati sa apara mesajul de login. Daca nu apare dupa 30 de secunde, apasati tasta 'enter' de 2 ori.

5. Introduceti numele de utilizator 'root' si parola nula.

6. Incepeti o sesiune de trasnfer prin comanda CTRL-a urmata de tasta 's'. Apasati enter.

7. Copiati scripturile frdm_imx95_provision.h (conectare wifi si extindere spatiu de stocare) si frdm_imx95_verify.sh specificand calea lor.

8. Permiteti executarea fisierelor.
```bash
chmod +x frdm_imx95_provision.sh frdm_imx95_verify.sh
```

9. Rulati scriptul frdm_imx95_provision.sh. Daca va apare eroare de test HTTPS, rulati scriptul din nou.

10. Rulati scriptul frdm_imx95_verify.sh

# Setup Docker
1. Descarcati imaginea de docker pe placa.
```bash
sudo docker pull remus03/imx95-ros2:imx
```

2. Creati un folder de workspace ros pe placa.
```bash
mkdir car_ws
```

3. Creati un container persitent.
```bash
docker run -it --name my_ros --network host -v ~/car_ws:/car_ws -v /dev:/dev --privileged remus03/imx95-ros2:imx
```

[aici]: https://www.nxp.com/document/guide/getting-started-with-frdm-imx95:GS-FRDM-IMX95