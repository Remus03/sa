# Setup iMX95
1. Instalati minicom pentru a avea o interfata cu placa de dezvoltare.
```bash
sudo apt install minicom
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

# Setup STM
1. Instalati [STM32CubeProgrammer].
2. Incarcati pe placuta binarul.

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
[STM32CubeProgrammer]: https://www.st.com/en/development-tools/stm32cubeprog.html

# Tema
1. Controlati robotul din tastatura/joystick. Puteti avea ca intrare numere intre -1.0 si 1.0 de la teleop_twist_keyboard, iar ca iesire numere intre 0 si 4095, trimise apoi pe seriala.

2. Controlati robotul printr-un controller open-loop, bazat pe Bicycle model. Intrarile trebuie sa fie referinte de viteza liniara si unghiulara. Iesirile trebuie sa fie comenzi pentru motorul DC is servomotor. Servomotorul urmareste deja referinta de unghi. Pentru motorul DC, trasati relatia intre comanda si viteza masinii.