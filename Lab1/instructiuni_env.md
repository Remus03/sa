# Introducere


## ROS2 si Gazebo
Scopul laboratorului de Sisteme Autonome este construierea fizica a unei masini la scara mica, capabila de navigare autonoma. Frameworkul utiliazat este [ROS2], atat pentru suportul comunitatii, ce ofera o multitudine de pachete, cat si pentru a facilita comunicarea intre modulele dezvoltate a curs.

In prima faza dar si simultan cu dezvoltarea fizica, simulatorul permite testarea anumitor module inainte de a le implementa pe platforma fizica.

Simulatorul utilizat in cadrul laboratorului este Gazebo, datorita integrarii sale mature in ecosistemul ROS. In continuare sunt prezentati pasii pentru a rula un model al masinii in simulator.

1. Instalare ROS2
    Instalati versiunea ros-humble-desktop si ros-dev-tools, urmarind pasii de la:
    https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html
<br>

2. Initiere environment ROS in terminal
    In mod implicit, environmentul de ROS trebuie initiat in fiecare sesiune noua de terminal. Pentru a face initierea autonomata, adaugati comanda in profilul terminalului:
    ```bash
    printf '\nsource /opt/ros/humble/setup.bash\n' >> ~/.bashrc
    ```
<br>

3. Instalare Gazebo
    ```bash
    sudo apt install ros-humble-gazebo-ros-pkgs
    ```
<br>

4. Lansare Gazebo
Gazebo trebuie lansat prin intermediului ROS pentru a comunica cu restul proceselor din mediu. Lansarea prin shortcutul aplicatiei nu ofera aceasta functionalitate.
    ```bash
    ros2 launch gazebo_ros gazebo.launch.py
    ```
<br>

5. Adaugarea masinii in mediu
    ```bash
    ros2 run gazebo_ros spawn_entity.py -entity my_robot -file <path/to/sdf> -x 0 -y 0 -z 0.1
    ```
<br>

6. Teleoperare prin pachetul teleop_twist_keyboard
    ```bash
    ros2 run teleop_twist_keyboard teleop_twist_keyboard
    ```
<br>

Pentru familirizarea cu mediul ROS2 si cu capabilitatile lui, parcurgeti urmatoarele tutoriale:
https://docs.ros.org/en/humble/First-Steps.html
https://docs.ros.org/en/humble/Tutorials/Beginner-CLI-Tools.html
https://docs.ros.org/en/humble/Tutorials/Beginner-Client-Libraries.html
https://docs.robotis.com/docs/systems/turtlebot3/simulation/navigation_simulation

## Docker
Container-ele permit impachetarea softwareului si a dependintelor pentru a fi instalate pe diferite sisteme de calcul fara modificari specifice platformei. In cadrul laboratului, mediul in care ruleaza programele pe masina va fi reprezentat de un container, ce poate fi rulat si pe dekstop.

1. Instalare Docker
    https://docs.docker.com/engine/install/ubuntu/
<br>

2. Descarcare imagine
    ```bash
    sudo docker pull remus03/imx95-ros2:imx
    ```
<br>

3. Pornirea containerului
    ```bash
    sudo docker run -it --rm remus03/imx95-ros2:imx
    ```
<br>





[ROS2]: https://docs.ros.org/en/humble/index.html