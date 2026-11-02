import copy
import math
import random

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node


def _quaternion_from_euler(roll, pitch, yaw):
	half_roll = roll / 2.0
	half_pitch = pitch / 2.0
	half_yaw = yaw / 2.0
	cos_roll = math.cos(half_roll)
	sin_roll = math.sin(half_roll)
	cos_pitch = math.cos(half_pitch)
	sin_pitch = math.sin(half_pitch)
	cos_yaw = math.cos(half_yaw)
	sin_yaw = math.sin(half_yaw)

	return (
		sin_roll * cos_pitch * cos_yaw - cos_roll * sin_pitch * sin_yaw,
		cos_roll * sin_pitch * cos_yaw + sin_roll * cos_pitch * sin_yaw,
		cos_roll * cos_pitch * sin_yaw - sin_roll * sin_pitch * cos_yaw,
		cos_roll * cos_pitch * cos_yaw + sin_roll * sin_pitch * sin_yaw,
	)


def _quaternion_multiply(quaternion1, quaternion0):
	x0, y0, z0, w0 = quaternion0
	x1, y1, z1, w1 = quaternion1
	return (
		w1 * x0 + x1 * w0 + y1 * z0 - z1 * y0,
		w1 * y0 - x1 * z0 + y1 * w0 + z1 * x0,
		w1 * z0 + x1 * y0 - y1 * x0 + z1 * w0,
		w1 * w0 - x1 * x0 - y1 * y0 - z1 * z0,
	)


class NoisyOdometry(Node):
	def __init__(self):
		super().__init__('noosify_odometry')
		self.declare_parameter('input_topic', '/odom')
		self.declare_parameter('output_topic', '/odom_noisy')
		self.declare_parameter('position_stddev', 0.05)
		self.declare_parameter('orientation_stddev', 0.02)
		self.declare_parameter('linear_velocity_stddev', 0.1)
		self.declare_parameter('angular_velocity_stddev', 0.04)
		self.declare_parameter('random_seed', -1)
		self.declare_parameter('publish_rate', 10.0)

		seed = self.get_parameter('random_seed').value
		self.rng = random.Random(None if seed < 0 else seed)
		input_topic = self.get_parameter('input_topic').value
		output_topic = self.get_parameter('output_topic').value
		self.publisher = self.create_publisher(Odometry, output_topic, 10)
		self.latest_message = None
		self.subscription = self.create_subscription(
			Odometry, input_topic, self.odometry_callback, 10
		)
		publish_rate = max(0.001, self.get_parameter('publish_rate').value)
		self.publish_timer = self.create_timer(
			1.0 / publish_rate, self.publish_latest_odometry
		)
		self.get_logger().info(f'Adding odometry noise: {input_topic} -> {output_topic}')

	def _noisy(self, value, stddev):
		return value + self.rng.gauss(0.0, max(0.0, stddev))

	def odometry_callback(self, message):
		self.latest_message = message

	def publish_latest_odometry(self):
		if self.latest_message is None:
			return

		noisy = copy.deepcopy(self.latest_message)

		position_std = self.get_parameter('position_stddev').value
		orientation_std = self.get_parameter('orientation_stddev').value
		linear_std = self.get_parameter('linear_velocity_stddev').value
		angular_std = self.get_parameter('angular_velocity_stddev').value
		position_variance = max(0.0, position_std) ** 2
		orientation_variance = max(0.0, orientation_std) ** 2
		linear_variance = max(0.0, linear_std) ** 2
		angular_variance = max(0.0, angular_std) ** 2

		# Independent Gaussian noise adds its variance to each covariance diagonal.
		pose_covariance = noisy.pose.covariance
		for index in (0, 7, 14):
			pose_covariance[index] += position_variance
		for index in (21, 28, 35):
			pose_covariance[index] += orientation_variance

		twist_covariance = noisy.twist.covariance
		for index in (0, 7, 14):
			twist_covariance[index] += linear_variance
		for index in (21, 28, 35):
			twist_covariance[index] += angular_variance

		position = noisy.pose.pose.position
		position.x = self._noisy(position.x, position_std)
		position.y = self._noisy(position.y, position_std)
		position.z = self._noisy(position.z, position_std)

		q = noisy.pose.pose.orientation
		perturbation = _quaternion_from_euler(
			self.rng.gauss(0.0, max(0.0, orientation_std)),
			self.rng.gauss(0.0, max(0.0, orientation_std)),
			self.rng.gauss(0.0, max(0.0, orientation_std)),
		)
		rotated = _quaternion_multiply((q.x, q.y, q.z, q.w), perturbation)
		norm = math.sqrt(sum(component * component for component in rotated))
		if norm > 0.0:
			q.x, q.y, q.z, q.w = (component / norm for component in rotated)
		else:
			q.x, q.y, q.z, q.w = perturbation

		linear = noisy.twist.twist.linear
		linear.x = self._noisy(linear.x, linear_std)
		linear.y = self._noisy(linear.y, linear_std)
		linear.z = self._noisy(linear.z, linear_std)
		angular = noisy.twist.twist.angular
		angular.x = self._noisy(angular.x, angular_std)
		angular.y = self._noisy(angular.y, angular_std)
		angular.z = self._noisy(angular.z, angular_std)

		self.publisher.publish(noisy)

	


def main(args=None):
	rclpy.init(args=args)
	node = NoisyOdometry()
	try:
		rclpy.spin(node)
	except KeyboardInterrupt:
		pass
	finally:
		node.destroy_node()
		rclpy.shutdown()


if __name__ == '__main__':
	main()
