"""
Launch the sam rover in Gazebo and Rviz.
ros2 launch ardupilot_sitl sitl_dds_udp.launch.py
command:=ardurover
transport:=udp4
synthetic_clock:=True
wipe:=False
model:=rover-skid
speedup:=1
slave:=0
instance:=0
refs:=$(ros2 pkg prefix ardupilot_sitl)/share/ardupilot_sitl/config/dds_xrce_profile.xml
defaults:=
    $(ros2 pkg prefix ardupilot_sitl)/share/ardupilot_sitl/config/default_params/rover.parm,
    $(ros2 pkg prefix ardupilot_sitl)/share/ardupilot_sitl/config/default_params/rover-skid.parm,
    $(ros2 pkg prefix ardupilot_sitl)/share/ardupilot_sitl/config/default_params/dds_udp.parm
sim_address:=127.0.0.1
master:=tcp:127.0.0.1:5760
sitl:=127.0.0.1:5501

"""

import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import IncludeLaunchDescription
from launch.actions import RegisterEventHandler

from launch.conditions import IfCondition

from launch.event_handlers import OnProcessStart

from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch.substitutions import PathJoinSubstitution

from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    """Generate a launch description for sam rover."""
    pkg_ardupilot_sitl = get_package_share_directory("ardupilot_sitl")
    pkg_ardupilot_sitl_models = get_package_share_directory("ardupilot_sitl_models")
    pkg_project_bringup = get_package_share_directory("sam_bringup")
    pkg_sam_sitl_models = get_package_share_directory("sam_sitl_models")

    # Include component launch files.
    sitl_dds = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            [
                PathJoinSubstitution(
                    [
                        FindPackageShare("ardupilot_sitl"),
                        "launch",
                        "sitl_dds_udp.launch.py",
                    ]
                ),
            ]
        ),
        launch_arguments={
            "command": "ardurover",
            "transport": "udp4",
            "synthetic_clock": "True",
            "port": "2019",
            "wipe": "False",
            "model": "rover",
            "speedup": "1",
            "slave": "0",
            "instance": "0",
            "refs": os.path.join(pkg_ardupilot_sitl, "config", "dds_xrce_profile.xml"),
            "defaults": os.path.join(
                pkg_ardupilot_sitl,
                "config",
                "default_params",
                "rover.parm",
            )
            + ","
            # +os.path.join(
            #     pkg_ardupilot_sitl,
            #     "config",
            #     "default_params",
            #     "rover-skid.parm",
            # )+ ","
            + os.path.join(
                pkg_ardupilot_sitl,
                "config",
                "default_params",
                "dds_udp.parm",
            ),
            "sim_address": "127.0.0.1",
            "master": "tcp:127.0.0.1:5760",
            "sitl": "127.0.0.1:5501",
        }.items(),
    )

    # Robot description.

    # Ensure `SDF_PATH` is populated as `sdformat_urdf`` uses this rather
    # than `GZ_SIM_RESOURCE_PATH` to locate resources.
    if "GZ_SIM_RESOURCE_PATH" in os.environ:
        gz_sim_resource_path = os.environ["GZ_SIM_RESOURCE_PATH"]

        if "SDF_PATH" in os.environ:
            sdf_path = os.environ["SDF_PATH"]
            os.environ["SDF_PATH"] = sdf_path + ":" + gz_sim_resource_path
        else:
            os.environ["SDF_PATH"] = gz_sim_resource_path

    # Load SDF file.
    sdf_file = os.path.join(
        pkg_sam_sitl_models, "models", "sam_model", "model.sdf"
    )
    with open(sdf_file, "r") as infp:
        robot_desc = infp.read()

        # substitute `models://` with `package://ardupilot_sitl_models/models/`
        # for sdformat_urdf plugin used by robot_state_publisher
        robot_desc = robot_desc.replace(
            "model://sam_model",
            "package://sam_sitl_models/models/sam_model")

        robot_desc = robot_desc.replace(
            "model://sam_model",
            "package://sam_sitl_models/models/sam_model")

    # Publish robot description for visualization in
    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        name="robot_state_publisher",
        output="both",
        parameters=[
            {"robot_description": robot_desc},
            {"frame_prefix": ""},
        ],
    )

    # Bridge.
    bridge = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        parameters=[
            {
                "config_file": os.path.join(
                    pkg_project_bringup, "config", "sam_bridge.yaml"
                ),
                "qos_overrides./tf_static.publisher.durability": "transient_local",
                "qos_overrides./pylon_camera_node/pylon_ros2_camera_node/camera_info.publisher.reliability": "best_effort",
                "qos_overrides./pylon_camera_node/pylon_ros2_camera_node/image_raw.publisher.reliability": "best_effort",
                "qos_overrides./camera/camera/color/camera_info.publisher.reliability": "best_effort",
                "qos_overrides./camera/camera/color/image_raw.publisher.reliability": "best_effort",
                "qos_overrides./sonar_left.publisher.reliability": "best_effort",
                "qos_overrides./sonar_right.publisher.reliability": "best_effort",
                "qos_overrides./sonar_back_mid.publisher.reliability": "best_effort",
                "qos_overrides./sonar_back_right.publisher.reliability": "best_effort",
                "qos_overrides./sonar_back_left.publisher.reliability": "best_effort",
                "qos_overrides./scan.publisher.reliability": "best_effort",
                "qos_overrides./simulation/odometry.publisher.reliability": "best_effort",
                "qos_overrides./camera/camera/imu.publisher.reliability": "best_effort",
            }
        ],
        output="screen",
    )

    # Relay - use instead of transform when Gazebo is only publishing odom -> base_link
    topic_tools_tf = Node(
        package="topic_tools",
        executable="relay",
        arguments=["/gz/tf", "/tf"],
        output="screen",
        respawn=False,
        # condition=IfCondition(LaunchConfiguration("use_gz_tf")),
    )

    return LaunchDescription(
        [
            sitl_dds,
            robot_state_publisher,
            bridge,
            RegisterEventHandler(
                OnProcessStart(target_action=bridge, on_start=[topic_tools_tf])
            ),
        ]
    )
