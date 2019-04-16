import rospy
from lowpass import LowPassFilter
from pid import PID
from yaw_controller import YawController


GAS_DENSITY = 2.858
ONE_MPH = 0.44704


class Controller(object):
    
    def __init__(self, vehicle_mass, fuel_capacity, brake_deadband, decel_limit,
                 accel_limit, wheel_radius, wheel_base, steer_ratio, max_lat_accel, max_steer_angle):
        
        self.yaw_controller = YawController(wheel_base, steer_ratio, 0.1, max_lat_accel, max_steer_angle)
        
        kp = 0.3
        ki = 0.1
        kd = 0.0
        mn = 0.0 # Minimum throttle value
        mx = 0.2 # Maximum throttle value, increase this if desired
        self.throttle_controller = PID(kp, ki, kd, mn, mx)
        
        tau = 0.5 # 1/(2pi*tau) = cutoff frequency
        ts = 0.02 # Sample time
        self.vel_lpf = LowPassFilter(tau, ts)
        
        self.vehicle_mass = vehicle_mass
        self.fuel_capacity = fuel_capacity
        self.brake_deadband = brake_deadband
        self.decel_limit = decel_limit
        self.accel_limit = accel_limit
        self.wheel_radius = wheel_radius
        
        self.last_time = rospy.get_time()

    
    def control(self, current_vel, dbw_enabled, linear_vel, angular_vel):
        
        if not dbw_enabled:
            self.throttle_controller.reset()
            return 0.0, 0.0, 0.0
        
        current_vel = self.vel_lpf.filt(current_vel)
        
        #rospy.logwarn("Angular velocity: {0}".format(angular_vel))
        #rospy.logwarn("Target linear velocity: {0}".format(linear_vel))
        #rospy.logwarn("Target angular velocity: {0}\n".format(angular_vel))
        #rospy.logwarn("Current velocity: {0}".format(current_vel))
        #rospy.logwarn("Filtered velocity: {0}".format(self.vel_lpf.get()))
        
        # **** Possibly add dampening terms below to reduce steering jerk when vehicle is wandering
        steering = self.yaw_controller.get_steering(linear_vel, angular_vel, current_vel)
        
        #rospy.logwarn("Steering: {0}".format(steering))
        
        vel_error = linear_vel - current_vel
        self.last_vel = current_vel
        
        current_time = rospy.get_time()
        sample_time = current_time - self.last_time
        self.last_time = current_time
        
        throttle = self.throttle_controller.step(vel_error, sample_time)
        brake = 0
        
        if linear_vel == 0.0 and current_vel < 0.1:
            throttle = 0
            # Changed from 400 Nm to 700 Nm per Udacity's specification of how much torque it would take
            #  to keep the vehicle stopped in gear with an automatic transmission
            brake = 700 #N*m - to hold the car in place if we are stopped at a light. Acceleration ~ lm/s^2
        elif throttle < 0.1 and vel_error < 0.0:
            throttle = 0
            decel = max(vel_error, self.decel_limit)
            brake = abs(decel)*self.vehicle_mass*self.wheel_radius # Torque N*m
            
        return throttle, brake, steering