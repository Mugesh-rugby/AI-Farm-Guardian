UPDATE treatments
SET notes = 'Farmer-entered plan from Rescue Planner. Review AI guidance before applying.'
WHERE notes LIKE 'Farmer-entered treatment from Rescue Planner. Review AI guidance before applying. Weather note:%';