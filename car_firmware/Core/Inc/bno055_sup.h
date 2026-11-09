#include "BNO055.h"
#include "stm32l4xx_hal.h"

#define BNO_RATE 100

extern I2C_HandleTypeDef hi2c1;

static int bno055_i2c_read(unsigned char dev_addr, unsigned char reg_addr,
                           unsigned char *data, unsigned char len)
{
  return (int)HAL_I2C_Mem_Read(&hi2c1, (uint16_t)(dev_addr << 1),
                               reg_addr, I2C_MEMADD_SIZE_8BIT,
                               data, len, 100);
}

static int bno055_i2c_write(unsigned char dev_addr, unsigned char reg_addr,
                            unsigned char *data, unsigned char len)
{
  return (int)HAL_I2C_Mem_Write(&hi2c1, (uint16_t)(dev_addr << 1),
                                reg_addr, I2C_MEMADD_SIZE_8BIT,
                                data, len, 100);
}

static void bno055_delay(unsigned int ms)
{
  HAL_Delay(ms);
}