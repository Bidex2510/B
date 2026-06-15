from sqlalchemy import Column, Integer, Float, String, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import datetime


class UserProfile(Base):
    __tablename__ = "user_profile"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, default="User")
    age = Column(Integer, default=25)
    weight_kg = Column(Float, default=70.0)
    height_cm = Column(Float, default=170.0)
    sex = Column(String, default="male")  # male / female
    activity_level = Column(String, default="moderate")  # sedentary/light/moderate/active/very_active
    goal = Column(String, default="maintain")  # lose/maintain/gain
    calorie_goal = Column(Integer, default=2000)
    protein_goal = Column(Integer, default=150)
    carbs_goal = Column(Integer, default=200)
    fat_goal = Column(Integer, default=65)
    water_goal_ml = Column(Integer, default=2500)
    created_at = Column(DateTime, default=func.now())

    food_logs = relationship("FoodLog", back_populates="user")
    weight_logs = relationship("WeightLog", back_populates="user")
    water_logs = relationship("WaterLog", back_populates="user")


class FoodItem(Base):
    __tablename__ = "food_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    brand = Column(String, nullable=True)
    barcode = Column(String, nullable=True, index=True)
    serving_size_g = Column(Float, default=100.0)
    serving_unit = Column(String, default="g")
    calories = Column(Float, default=0)
    protein_g = Column(Float, default=0)
    carbs_g = Column(Float, default=0)
    fat_g = Column(Float, default=0)
    fiber_g = Column(Float, default=0)
    sugar_g = Column(Float, default=0)
    sodium_mg = Column(Float, default=0)
    usda_fdc_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())


class FoodLog(Base):
    __tablename__ = "food_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user_profile.id"), default=1)
    food_item_id = Column(Integer, ForeignKey("food_items.id"))
    date = Column(Date, default=datetime.date.today)
    meal_type = Column(String, default="lunch")  # breakfast/lunch/dinner/snack
    quantity_g = Column(Float, default=100.0)
    # Calculated at log time
    calories = Column(Float, default=0)
    protein_g = Column(Float, default=0)
    carbs_g = Column(Float, default=0)
    fat_g = Column(Float, default=0)
    created_at = Column(DateTime, default=func.now())

    user = relationship("UserProfile", back_populates="food_logs")
    food_item = relationship("FoodItem")


class WeightLog(Base):
    __tablename__ = "weight_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user_profile.id"), default=1)
    date = Column(Date, default=datetime.date.today)
    weight_kg = Column(Float)
    created_at = Column(DateTime, default=func.now())

    user = relationship("UserProfile", back_populates="weight_logs")


class WaterLog(Base):
    __tablename__ = "water_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user_profile.id"), default=1)
    date = Column(Date, default=datetime.date.today)
    amount_ml = Column(Integer, default=250)
    created_at = Column(DateTime, default=func.now())

    user = relationship("UserProfile", back_populates="water_logs")


class SavedMeal(Base):
    __tablename__ = "saved_meals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    items = Column(Text)  # JSON list of {food_item_id, quantity_g, meal_type}
    total_calories = Column(Float, default=0)
    created_at = Column(DateTime, default=func.now())
