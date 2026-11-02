import argparse
import math

import matplotlib.pyplot as plt
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message


def integrate_imu(samples):
	"""Roteste informatia IMU in sistemul de referinta global si integreaza"""
	x = y = vx = vy = 0.0
	result = []
	previous_t = None
	for t, msg in samples:
		q = msg.orientation
		ax, ay, az = (msg.linear_acceleration.x, msg.linear_acceleration.y,
					  msg.linear_acceleration.z)
		tx, ty, tz = (2 * (q.y * az - q.z * ay),
					  2 * (q.z * ax - q.x * az),
					  2 * (q.x * ay - q.y * ax))
		world_ax = ax + q.w * tx + q.y * tz - q.z * ty
		world_ay = ay + q.w * ty + q.z * tx - q.x * tz
		if previous_t is not None:
			dt = t - previous_t
			if dt > 0:
				x += vx * dt + 0.5 * world_ax * dt * dt
				y += vy * dt + 0.5 * world_ay * dt * dt
				vx += world_ax * dt
				vy += world_ay * dt
		result.append((t, x, y))
		previous_t = t
	return result


def integrate_cmd_vel(samples, prediction_period=0.05):
	"""Roteste informatia de viteza in sistemul de referinta global si integreaza"""
	if not samples:
		return []

	x = y = yaw = 0.0
	result = [(samples[0][0], x, y)]
	previous_t = samples[0][0]
	next_prediction = previous_t + prediction_period
	first_twist = samples[0][1].twist if hasattr(samples[0][1], "twist") else samples[0][1]
	vx, vy, wz = first_twist.linear.x, first_twist.linear.y, first_twist.angular.z

	def advance(t):
		nonlocal x, y, yaw, previous_t
		dt = t - previous_t
		if dt <= 0:
			return
		mid_yaw = yaw + wz * dt / 2
		x += (vx * math.cos(mid_yaw) - vy * math.sin(mid_yaw)) * dt
		y += (vx * math.sin(mid_yaw) + vy * math.cos(mid_yaw)) * dt
		yaw += wz * dt
		previous_t = t

	for t, msg in samples[1:]:
		while next_prediction <= t:
			advance(next_prediction)
			result.append((next_prediction, x, y))
			next_prediction += prediction_period
		advance(t)
		if result[-1][0] != t:
			result.append((t, x, y))
		twist = msg.twist if hasattr(msg, "twist") else msg
		vx, vy, wz = twist.linear.x, twist.linear.y, twist.angular.z
	return result


def position_errors(points, ground_truth):
	"""Return Euclidean position errors at estimate timestamps."""
	if not points or not ground_truth:
		return []

	errors = []
	gt_index = 0
	for t, x, y in points:
		if t < ground_truth[0][0] or t > ground_truth[-1][0]:
			continue
		while (gt_index + 1 < len(ground_truth)
			   and ground_truth[gt_index + 1][0] < t):
			gt_index += 1

		t0, x0, y0 = ground_truth[gt_index]
		if gt_index + 1 < len(ground_truth):
			t1, x1, y1 = ground_truth[gt_index + 1]
			if t1 > t0:
				fraction = (t - t0) / (t1 - t0)
				gt_x = x0 + fraction * (x1 - x0)
				gt_y = y0 + fraction * (y1 - y0)
			else:
				gt_x, gt_y = x0, y0
		else:
			gt_x, gt_y = x0, y0
		errors.append((t, math.hypot(x - gt_x, y - gt_y)))
	return errors


def main():
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("bag", help="ROS2 bag")
	args = parser.parse_args()

	reader = rosbag2_py.SequentialReader()
	reader.open(
		rosbag2_py.StorageOptions(uri=args.bag, storage_id=""),
		rosbag2_py.ConverterOptions("", ""),
	)
	
	topic_types = {topic.name: topic.type for topic in reader.get_all_topics_and_types()}
	topics = {
		"imu": ("/imu", True),
		"odom": ("/odom_noisy", True),
		"odom_filtered": ("/odometry/filtered", True),
		"ground_truth": ("/odom", True),
		"cmd_vel": ("/cmd_vel", True),
	}
	enabled_topics = {
		key: name for key, (name, enabled) in topics.items() if enabled
	}
	topic_to_key = {name: key for key, name in enabled_topics.items()}
	
	messages = {key: [] for key in topics}
	message_types = {
		name: get_message(topic_types[name])
		for name in enabled_topics.values()
		if name in topic_types
	}
	start = None
	
	while reader.has_next():
		topic, serialized, stamp = reader.read_next()
		if topic not in message_types:
			continue
		if start is None:
			start = stamp
		t = (stamp - start) * 1e-9
		key = topic_to_key[topic]
		msg = deserialize_message(serialized, message_types[topic])
		messages[key].append((t, msg))

	odom = [(t, msg.pose.pose.position.x, msg.pose.pose.position.y)
			for t, msg in messages["odom"]]
	odom_filtered = [(t, msg.pose.pose.position.x, msg.pose.pose.position.y)
				 for t, msg in messages["odom_filtered"]]
	ground_truth = [(t, msg.pose.pose.position.x, msg.pose.pose.position.y)
				for t, msg in messages["ground_truth"]]
	estimates = (
		("Acceleratie IMU (integrat de 2 ori)", integrate_imu(messages["imu"])),
		("GPS", odom),
		("Kalman", odom_filtered),
		("Comanda (integrata)", integrate_cmd_vel(messages["cmd_vel"])),
	)
	error_data = [position_errors(points, ground_truth) for _, points in estimates]
	max_error = max(
		(error for errors in error_data for _, error in errors),
		default=0.0,
	)
	error_ylim = max_error if max_error > 0 else 1.0

	for (label, points), errors in zip(estimates, error_data):
		if not points:
			print(f"Fara date {label}")
			continue
		if errors:
			fig, (ax, error_ax) = plt.subplots(
				2, 1, gridspec_kw={"height_ratios": [2, 1]}
			)
		else:
			fig, ax = plt.subplots()
		x0, y0 = points[0][1:]
		ax.plot([p[2] - y0 for p in points], [p[1] - x0 for p in points], label=label)
		if ground_truth:
			gt_x0, gt_y0 = ground_truth[0][1:]
			ax.plot([p[2] - gt_y0 for p in ground_truth],
					[p[1] - gt_x0 for p in ground_truth], label="Ground truth")
		ax.set(title=f"Pozitie estimata: {label}", xlabel="y", ylabel="x")
		ax.axis("equal")
		ax.grid(True)
		ax.legend()
		if errors:
			error_ax.plot([t for t, _ in errors], [error for _, error in errors],
					     label=f"Eroare {label}")
			error_ax.set(title=f"Eroare de pozitie: {label}",
					   xlabel="Timp (s)", ylabel="Eroare (m)", ylim=(0, error_ylim))
			error_ax.grid(True)
			error_ax.legend()
		fig.tight_layout()
	plt.show()


if __name__ == "__main__":
	main()
