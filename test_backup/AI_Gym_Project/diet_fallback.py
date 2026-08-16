import random
import re

FOOD_DB = {
    "breakfast_carbs": [
        {"item": "Oats", "quantity": "60 g", "calories": 230, "protein": 8, "carbs": 40, "fat": 4, "tags": ["veg", "vegan"]},
        {"item": "Idli", "quantity": "3 pieces", "calories": 180, "protein": 5, "carbs": 38, "fat": 1, "tags": ["veg", "vegan"]},
        {"item": "Dosa", "quantity": "1 medium", "calories": 130, "protein": 3, "carbs": 25, "fat": 2, "tags": ["veg", "vegan"]},
        {"item": "Poha", "quantity": "1.5 cups", "calories": 260, "protein": 5, "carbs": 45, "fat": 6, "tags": ["veg", "vegan"]},
        {"item": "Upma", "quantity": "1.5 cups", "calories": 250, "protein": 6, "carbs": 40, "fat": 7, "tags": ["veg", "vegan"]},
        {"item": "Whole Wheat Bread", "quantity": "2 slices", "calories": 150, "protein": 6, "carbs": 28, "fat": 2, "tags": ["veg", "vegan"]},
    ],
    "main_carbs": [
        {"item": "Cooked Rice", "quantity": "150 g", "calories": 195, "protein": 4, "carbs": 42, "fat": 0, "tags": ["veg", "vegan"]},
        {"item": "Roti", "quantity": "2 pieces", "calories": 220, "protein": 6, "carbs": 45, "fat": 2, "tags": ["veg", "vegan"]},
        {"item": "Chapati", "quantity": "2 pieces", "calories": 200, "protein": 6, "carbs": 40, "fat": 2, "tags": ["veg", "vegan"]},
        {"item": "Sweet Potato", "quantity": "150 g", "calories": 130, "protein": 2, "carbs": 30, "fat": 0, "tags": ["veg", "vegan"]},
        {"item": "Quinoa", "quantity": "100 g cooked", "calories": 120, "protein": 4, "carbs": 21, "fat": 2, "tags": ["veg", "vegan"]},
    ],
    "proteins_veg": [
        {"item": "Paneer", "quantity": "100 g", "calories": 290, "protein": 18, "carbs": 3, "fat": 22, "tags": ["veg"]},
        {"item": "Tofu", "quantity": "100 g", "calories": 140, "protein": 15, "carbs": 3, "fat": 8, "tags": ["veg", "vegan"]},
        {"item": "Dal (Lentils)", "quantity": "1 bowl (cooked)", "calories": 180, "protein": 12, "carbs": 30, "fat": 1, "tags": ["veg", "vegan"]},
        {"item": "Chickpeas (Chole)", "quantity": "1 bowl (cooked)", "calories": 220, "protein": 11, "carbs": 35, "fat": 4, "tags": ["veg", "vegan"]},
        {"item": "Rajma (Kidney Beans)", "quantity": "1 bowl (cooked)", "calories": 210, "protein": 11, "carbs": 35, "fat": 2, "tags": ["veg", "vegan"]},
        {"item": "Sprouts", "quantity": "1 cup", "calories": 100, "protein": 8, "carbs": 18, "fat": 1, "tags": ["veg", "vegan"]},
        {"item": "Greek Yogurt", "quantity": "150 g", "calories": 100, "protein": 15, "carbs": 5, "fat": 0, "tags": ["veg"]},
        {"item": "Curd (Yogurt)", "quantity": "1 bowl", "calories": 150, "protein": 6, "carbs": 10, "fat": 8, "tags": ["veg"]},
    ],
    "proteins_nonveg": [
        {"item": "Chicken Breast", "quantity": "150 g", "calories": 165, "protein": 31, "carbs": 0, "fat": 3, "tags": ["non-veg"]},
        {"item": "Fish (Tilapia/Rohu)", "quantity": "150 g", "calories": 145, "protein": 30, "carbs": 0, "fat": 2, "tags": ["non-veg"]},
        {"item": "Eggs", "quantity": "2 whole", "calories": 140, "protein": 12, "carbs": 1, "fat": 10, "tags": ["non-veg", "eggitarian"]},
        {"item": "Egg Whites", "quantity": "4 large", "calories": 70, "protein": 14, "carbs": 1, "fat": 0, "tags": ["non-veg", "eggitarian"]},
    ],
    "vegetables": [
        {"item": "Mixed Vegetables", "quantity": "1 cup", "calories": 50, "protein": 2, "carbs": 10, "fat": 0, "tags": ["veg", "vegan"]},
        {"item": "Spinach", "quantity": "1 cup cooked", "calories": 40, "protein": 5, "carbs": 7, "fat": 0, "tags": ["veg", "vegan"]},
        {"item": "Broccoli", "quantity": "1 cup", "calories": 55, "protein": 4, "carbs": 11, "fat": 0, "tags": ["veg", "vegan"]},
        {"item": "Cucumber & Tomato Salad", "quantity": "1 bowl", "calories": 30, "protein": 1, "carbs": 7, "fat": 0, "tags": ["veg", "vegan"]},
        {"item": "Green Beans", "quantity": "1 cup", "calories": 45, "protein": 2, "carbs": 10, "fat": 0, "tags": ["veg", "vegan"]},
    ],
    "fats": [
        {"item": "Almonds", "quantity": "15 g", "calories": 90, "protein": 3, "carbs": 3, "fat": 8, "tags": ["veg", "vegan"]},
        {"item": "Walnuts", "quantity": "15 g", "calories": 95, "protein": 2, "carbs": 2, "fat": 10, "tags": ["veg", "vegan"]},
        {"item": "Mixed Seeds", "quantity": "1 tbsp", "calories": 60, "protein": 2, "carbs": 2, "fat": 5, "tags": ["veg", "vegan"]},
        {"item": "Olive Oil (cooking)", "quantity": "1 tsp", "calories": 40, "protein": 0, "carbs": 0, "fat": 5, "tags": ["veg", "vegan"]},
        {"item": "Peanut Butter", "quantity": "1 tbsp", "calories": 95, "protein": 4, "carbs": 3, "fat": 8, "tags": ["veg", "vegan"]},
        {"item": "Groundnut Chutney", "quantity": "2 tbsp", "calories": 80, "protein": 3, "carbs": 4, "fat": 6, "tags": ["veg", "vegan"]}
    ],
    "fruits_snacks": [
        {"item": "Apple", "quantity": "1 medium", "calories": 95, "protein": 0, "carbs": 25, "fat": 0, "tags": ["veg", "vegan"]},
        {"item": "Banana", "quantity": "1 medium", "calories": 105, "protein": 1, "carbs": 27, "fat": 0, "tags": ["veg", "vegan"]},
        {"item": "Orange", "quantity": "1 medium", "calories": 60, "protein": 1, "carbs": 15, "fat": 0, "tags": ["veg", "vegan"]},
        {"item": "Papaya", "quantity": "1 cup", "calories": 60, "protein": 1, "carbs": 15, "fat": 0, "tags": ["veg", "vegan"]},
        {"item": "Roasted Makhana", "quantity": "30 g", "calories": 110, "protein": 3, "carbs": 22, "fat": 1, "tags": ["veg", "vegan"]},
    ]
}

def filter_db(user_data: dict) -> dict:
    pref = user_data.get("dietary_preference", "No Restriction").lower()
    allergies = user_data.get("allergies", "")
    allergy_list = [a.strip().lower() for a in allergies.split(",") if a.strip()]
    if "none" in allergy_list:
        allergy_list.remove("none")
        
    filtered = {}
    for category, items in FOOD_DB.items():
        filtered_items = []
        for item in items:
            # Check dietary preference
            if pref == "vegan" and "vegan" not in item["tags"]:
                continue
            if pref == "vegetarian" and "veg" not in item["tags"]:
                continue
            if pref == "eggitarian" and "eggitarian" not in item["tags"] and "veg" not in item["tags"]:
                continue
                
            # Check allergies
            item_lower = item["item"].lower()
            allergy_match = False
            for allergy in allergy_list:
                if allergy in item_lower:
                    allergy_match = True
                    break
                # Special peanut handling since it's a very common requirement
                if allergy == "peanuts" and ("peanut" in item_lower or "groundnut" in item_lower):
                    allergy_match = True
                    break
                    
            if not allergy_match:
                filtered_items.append(item)
                
        filtered[category] = filtered_items
        
    return filtered

def generate_fallback_diet_plan(user_data: dict, target_macros: dict) -> dict:
    # 1. Filter database based on constraints
    db = filter_db(user_data)
    
    meals_per_day = int(user_data.get("meals_per_day", 4))
    target_cals = float(target_macros["calories"])
    
    # 2. Distribute target calories across meals
    if meals_per_day == 3:
        splits = [0.35, 0.40, 0.25]
        names = ["Breakfast", "Lunch", "Dinner"]
    elif meals_per_day == 4:
        splits = [0.25, 0.30, 0.15, 0.30]
        names = ["Breakfast", "Lunch", "Snack", "Dinner"]
    elif meals_per_day == 5:
        splits = [0.20, 0.25, 0.15, 0.25, 0.15]
        names = ["Breakfast", "Lunch", "Afternoon Snack", "Dinner", "Evening Snack"]
    else:
        # Fallback distribution
        splits = [1.0 / meals_per_day] * meals_per_day
        names = [f"Meal {i+1}" for i in range(meals_per_day)]
        
    plan = {"days": []}
    
    for day in range(1, 8):
        day_meals = []
        for meal_idx in range(meals_per_day):
            meal_cals_target = target_cals * splits[meal_idx]
            meal_name = names[meal_idx]
            
            # Select categories based on meal type
            is_veg = user_data.get("dietary_preference", "").lower() in ["vegan", "vegetarian"]
            if "Breakfast" in meal_name:
                protein_cat = "proteins_veg" if is_veg else random.choice(["proteins_veg", "proteins_nonveg"])
                categories = ["breakfast_carbs", protein_cat]
            elif "Snack" in meal_name:
                categories = ["fruits_snacks", "fats"]
            else:
                protein_cat = "proteins_veg" if is_veg else random.choice(["proteins_veg", "proteins_nonveg"])
                categories = ["main_carbs", protein_cat, "vegetables"]
            
            foods = []
            total_cals = 0
            total_p = 0
            total_c = 0
            total_f = 0
            
            # First pass: add 1 standard serving of each selected category
            for cat in categories:
                if db.get(cat):
                    food = random.choice(db[cat])
                    # Ensure we don't pick the same food twice in one meal
                    if not any(f["item"] == food["item"] for f in foods):
                        foods.append(food.copy())
                        total_cals += food["calories"]
                        total_p += food["protein"]
                        total_c += food["carbs"]
                        total_f += food["fat"]
                        
            # Second pass: adjust quantities using a multiplier to reach the calorie target
            if total_cals > 0:
                multiplier = meal_cals_target / total_cals
                
                # Keep multiplier reasonable (between 0.5 and 2.5) to avoid absurd portions
                multiplier = max(0.5, min(2.5, multiplier))
                
                scaled_cals = 0
                scaled_p = 0
                scaled_c = 0
                scaled_f = 0
                
                formatted_foods = []
                for f in foods:
                    # scale macros
                    fc = int(f["calories"] * multiplier)
                    fp = int(f["protein"] * multiplier)
                    fcar = int(f["carbs"] * multiplier)
                    ffat = int(f["fat"] * multiplier)
                    
                    scaled_cals += fc
                    scaled_p += fp
                    scaled_c += fcar
                    scaled_f += ffat
                    
                    # Try to scale the quantity string cleanly if possible
                    qty_str = f["quantity"]
                    match = re.search(r'^([0-9.]+)\s*(.*)', qty_str)
                    if match:
                        num = float(match.group(1))
                        unit = match.group(2)
                        new_num = round(num * multiplier, 1)
                        if new_num.is_integer():
                            new_num = int(new_num)
                        new_qty_str = f"{new_num} {unit}"
                    else:
                        new_qty_str = f"{qty_str} (x{round(multiplier, 1)})"
                        
                    formatted_foods.append({
                        "item": f["item"],
                        "quantity": new_qty_str
                    })
            else:
                formatted_foods = []
                scaled_cals = 0
                scaled_p = 0
                scaled_c = 0
                scaled_f = 0

            day_meals.append({
                "name": meal_name,
                "foods": formatted_foods,
                "calories": scaled_cals,
                "protein": scaled_p,
                "carbs": scaled_c,
                "fat": scaled_f
            })
            
        plan["days"].append({
            "day": day,
            "meals": day_meals
        })
        
    return plan
