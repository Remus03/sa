import numpy as np
import matplotlib.pyplot as plt

x = np.array([0, 1])

P = np.array([[3, 0], 
              [0, 3]])

Q = np.array([[0.1, 0],
              [0, 0.1]])

R = 0.5

H = np.array([[1, 0]])


def predict(x, P, Q, dt):

    F = np.array([[1, dt],
                  [0, 1]])

    x_apr = F @ x
    P_apr = F @ P @ F.T + Q

    return x_apr, P_apr

def update(x, P, z):

    y = z - H @ x
    S = H @ P @ H.T + R
    K = P @ H.T @ np.linalg.inv(S)

    x_upd = x + K @ y
    P_upd = (np.eye(len(x)) - K @ H) @ P

    return x_upd, P_upd


def plot_state_distribution(state, P):
    plt.clf()
    mean = state[0]
    variance = P[0, 0]
    standard_deviation = np.sqrt(variance)
    positions = np.linspace(mean - 4 * standard_deviation,
                            mean + 4 * standard_deviation, 300)
    density = np.exp(-0.5 * ((positions - mean) / standard_deviation) ** 2)
    density /= standard_deviation * np.sqrt(2 * np.pi)

    plt.plot(positions, density)
    plt.xlim(-4, 20)
    plt.ylim(0, 2)
    plt.title("Position distribution")
    plt.xlabel("Position")
    plt.ylabel("Probability density")
    plt.tight_layout()
    plt.show(block=False)


if __name__ == "__main__":
    dt = 1.0
    measurements = [0.9, 2.1, 3.0, 4.2, 5.1,
                    6.0, 7.2, 8.0, 9.1, 10.2,
                    11.0, 12.1, 13.2, 14.0, 15.1]

    plot_state_distribution(x, P)

    for z in measurements:
        x, P = predict(x, P, Q, dt)
        x, P = update(x, P, z)

        input("Apasa enter pentru a continua")
        plot_state_distribution(x, P)
        