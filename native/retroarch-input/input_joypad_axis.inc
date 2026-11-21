static int16_t input_joypad_axis(
      float input_analog_deadzone,
      float input_analog_sensitivity,
      const input_device_driver_t *drv,
      unsigned port, uint32_t joyaxis, float normal_mag)
{
   int16_t val = ((joyaxis != AXIS_NONE) && drv && drv->axis) ? drv->axis(port, joyaxis) : 0;

   if (input_analog_deadzone)
   {
      /* if analog value is below the deadzone, ignore it
       * normal magnitude is calculated radially for analog sticks
       * and linearly for analog buttons */
      if (normal_mag <= input_analog_deadzone)
         return 0;

      /* due to the way normal_mag is calculated differently for buttons and
       * sticks, this results in either a radial scaled deadzone for sticks
       * or linear scaled deadzone for analog buttons */
      val = val * MAX(1.0f,(1.0f / normal_mag)) * MIN(1.0f,
            ((normal_mag - input_analog_deadzone)
          / (1.0f - input_analog_deadzone)));
   }

   if (input_analog_sensitivity != 1.0f)
   {
      float normalized = (1.0f / 0x7fff) * val;
      int      new_val = 0x7fff * normalized * input_analog_sensitivity;
      if (new_val > 0x7fff)
         return 0x7fff;
      else if (new_val < -0x7fff)
         return -0x7fff;
      return new_val;
   }

   return val;
}
