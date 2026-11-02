# EKF Robot Localization

## Colectarea datelor
1. Deschideti Gazebo
    ```bash
    ros2 launch gazebo_ros gazebo.launch.py
    ```
<br>

2. Adaugarea masinia.
    ```bash
    ros2 run gazebo_ros spawn_entity.py -entity sa_car -file <path/to/sdf> -x 0 -y 0 -z 0.1
    ```
<br>

3. Lansati in executie nodul din pachetul de ros lab5. Acesta va oferi date similare unui sistem de GPS/UWB.
    ```bash
    ros2 run lab5 noisify_odom
    ```
<br>

4. Porniti inregistrare datelor.
    ```bash
    ros2 bag record -a
    ```
<br>

5. Dupa deplasarea masinii, opriti colectia de date cu CTRL-C. Introduceti calea catre bag-ul de date ca paramentru de linie de comanda pentru plot_rosbag.py

## Filtrarea datelor

1. Rulati nodul de EKF din pachetul robot_localization.
    ```bash
    ros2 run robot_localization ekf_node --ros-args --params-file /home/remus/sa_ws/src/lab5/params/ekf.yaml
    ```
<br>

2. Porniti inregistrare datelor.
    ```bash
    ros2 bag record -a
    ```
<br>

3. Porniti redarea datelor de intrare in filtru.
    ```bash
    ros2 play <path/to/bag/directory>
    ```
<br>

4. Introduceti calea catre bag-ul cu iesirea filtrului ca paramentru de linie de comanda pentru plot_rosbag.py

# Tema
Implementati un EKF (Extended Kalman Filter) pentru deplasarea unui robot pe un plan. Vectroul de stare va fi format din pozitie si viteza ( [x,y,yaw,vx, vy, vyaw] ). Comanda va fi data in sistemul de coordnate al masinii. Corectia va fi facuta printr-un sistem GPS simulat ce ofera pozitie si orientare. 

Implementati:
* Un model de miscare adecvat 0.1p
* Zgomot de proces 0.2p
* Zgomot de masurares 0.2p
* Pasul de estimare 0.2p
* Pasul de corectie 0.2p
* O convergenta sesizabila a inceritudinii 0.1p