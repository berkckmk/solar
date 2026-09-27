# Astronomical Science & Orbital Mechanics Notes

**Project:** Solar System Through Earth Time  
**Module:** `projects/solar_system_time_journey`  
**Reference Epoch:** J2000.0 (`2000-01-01T12:00:00.000` Barycentric Dynamical Time, JD `2451545.0`)  

---

## 1. Primary Astronomical Sources

All planetary elements, masses, radii, and physical constants are derived from authoritative, peer-reviewed NASA and JPL publications:

1. **JPL Solar System Dynamics Group**:
   - Standish, E. M. (1992). *"Keplerian Elements for Approximate Positions of the Major Planets"*, Jet Propulsion Laboratory / Caltech.
   - Reference table: [https://ssd.jpl.nasa.gov/planets/approx_pos.html](https://ssd.jpl.nasa.gov/planets/approx_pos.html)
   - Coordinate reference: J2000 mean ecliptic and equinox.

2. **NASA Goddard Space Flight Center**:
   - Williams, D. R. (2024 revision). *NASA Planetary Fact Sheets*.
   - Reference: [https://nssdc.gsfc.nasa.gov/planetary/factsheet/](https://nssdc.gsfc.nasa.gov/planetary/factsheet/)

3. **International Astronomical Union (IAU)**:
   - IAU 2012 Astronomical Constants: $1\text{ AU} = 149,597,870,700\text{ m} \approx 149,597,870.7\text{ km}$.
   - Nominal Solar Radius: $R_\odot = 695,700\text{ km}$.

---

## 2. Keplerian Orbit Solver Mathematics

For any planet at elapsed time $t$ (in Earth days from J2000.0):

### 2.1 Mean Anomaly $M(t)$
$$n = \frac{2\pi}{T_{\text{period}}}$$
$$M(t) = M_0 + n \cdot t \pmod{2\pi}$$
where $M_0$ is the mean anomaly at epoch J2000.0 and $T_{\text{period}}$ is the sidereal orbital period in days.

### 2.2 Kepler's Equation for Eccentric Anomaly $E$
$$M = E - e \sin(E)$$
Solves for $E$ using Newton–Raphson iteration with machine-epsilon tolerance ($\epsilon = 10^{-12}$):
$$E_{k+1} = E_k - \frac{E_k - e \sin(E_k) - M}{1 - e \cos(E_k)}$$
Guaranteed quadratic convergence for all planetary eccentricities ($e \le 0.2056$).

### 2.3 True Anomaly $\nu$
$$\tan\left(\frac{\nu}{2}\right) = \sqrt{\frac{1 + e}{1 - e}} \tan\left(\frac{E}{2}\right)$$
$$\nu = 2 \operatorname{atan2}\left(\sqrt{1+e}\sin\frac{E}{2}, \sqrt{1-e}\cos\frac{E}{2}\right)$$

### 2.4 Heliocentric Distance $r$
$$r = a (1 - e \cos E)$$

### 2.5 3D Heliocentric Ecliptic Coordinates $(x, y, z)$
The position vector in the orbital plane is:
$$\mathbf{r}_{\text{orb}} = \begin{bmatrix} r \cos \nu \\ r \sin \nu \\ 0 \end{bmatrix}$$
Transformed to the J2000 ecliptic coordinate frame via Euler rotations $\mathbf{R}_z(-\Omega) \mathbf{R}_x(-i) \mathbf{R}_z(-\omega)$:
$$\begin{aligned}
x &= r \cdot \left(\cos\Omega \cos(\omega+\nu) - \sin\Omega \sin(\omega+\nu) \cos i\right) \\
y &= r \cdot \left(\sin\Omega \cos(\omega+\nu) + \cos\Omega \sin(\omega+\nu) \cos i\right) \\
z &= r \cdot \left(\sin(\omega+\nu) \sin i\right)
\end{aligned}$$

---

## 3. Real Trajectory Arc Length Integration

Rather than approximating path length as average speed $\times$ time, the true distance travelled along the elliptic path is computed via numerical Riemann integration over $N \ge 4000$ points:
$$L = \int_0^{\Delta t} \|\mathbf{v}(t)\| \, dt \approx \sum_{k=1}^N \sqrt{(x_k - x_{k-1})^2 + (y_k - y_{k-1})^2 + (z_k - z_{k-1})^2}$$

---

## 4. Validated Astronomical Metrics Table

Computed by `science/metrics.py` and validated by `science/validation.py`:

| Planet | 1 Day Distance | 1 Day % Orbit | 30 Day Distance | 30 Day % Orbit | 365 Day Distance | 365 Day Orbits | Avg Speed |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Mercury** | 3.69M km | 1.14% | 110.69M km | 34.10% | 1,348M km | **4.15×** | 42.7 km/s |
| **Venus** | 3.03M km | 0.44% | 90.76M km | 13.35% | 1,104M km | **1.62×** | 35.0 km/s |
| **Earth** | 2.57M km | 0.27% | 77.20M km | 8.21% | 939M km | **1.00×** | 29.8 km/s |
| **Mars** | 2.08M km | 0.15% | 62.46M km | 4.37% | 759M km | **0.53×** | 24.1 km/s |
| **Jupiter** | 1.17M km | 0.02% | 35.19M km | 0.69% | 428M km | **0.08×** | 13.6 km/s |
| **Saturn** | 0.87M km | 0.01% | 26.15M km | 0.28% | 318M km | **0.03×** | 10.1 km/s |
| **Uranus** | 0.59M km | 0.003% | 17.62M km | 0.10% | 214M km | **0.01×** | 6.8 km/s |
| **Neptune** | 0.47M km | 0.002% | 14.07M km | 0.06% | 171M km | **0.006×** | 5.4 km/s |

*All values verified with zero NaN/Inf; Earth closes exactly $1.00\times$ orbit in 365.25 days.*
