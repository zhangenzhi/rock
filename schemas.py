"""
此文件集中定义了项目中所有与Gemini API交互所需的JSON Schema。
这确保了AI返回的数据结构是可预测且被强制约束的。
"""

# 通用类型定义
STRING = {"type": "STRING"}
NUMBER = {"type": "NUMBER"}
BOOLEAN = {"type": "BOOLEAN"}
ARRAY = {"type": "ARRAY"}
OBJECT = {"type": "OBJECT"}

# --- 基础 Schema ---
MOVIE_SELECTION_SCHEMA = {
    "type": OBJECT,
    "properties": { "movie_name": STRING }
}

TOOL_CREATION_SCHEMA = {
    "type": OBJECT,
    "properties": {
        "tool_name": STRING,
        "description": STRING,
        "potential_use": STRING
    }
}

REVIEW_SCHEMA = {
    "type": OBJECT,
    "properties": {
        "review_points": {
            "type": ARRAY,
            "items": STRING
        }
    }
}

# --- 章节与故事数据 Schema ---
CHARACTER_PROFILE_SCHEMA = {
    "type": OBJECT,
    "properties": {
        "background": STRING,
        "motivation": STRING,
        "outlook": STRING
    }
}

UPDATED_CHARACTER_PROFILE_SCHEMA = {
    "type": OBJECT,
    "properties": {
        "background": STRING,
        "motivation": STRING,
        "outlook": STRING,
        "recent_observations": STRING
    }
}

CHAPTER_GENERATION_SCHEMA = {
    "type": OBJECT,
    "properties": {
        "title": STRING,
        "pov_character": STRING,
        "paragraphs": {
            "type": ARRAY,
            "items": STRING
        }
    }
}

# --- 规划与决策 Schema ---
SCENE_SCHEMA = {
    "type": OBJECT,
    "properties": {
        "scene_number": NUMBER,
        "day": NUMBER,
        "part_of_day": STRING,
        "subtitle": STRING,
        "synopsis": STRING,
        "pov_character": STRING,
        "emotion_anchor": STRING
    }
}

CHARACTER_POOL_ITEM_SCHEMA = {
    "type": OBJECT,
    "properties": {
        "name": STRING,
        "personality": STRING,
        "function": STRING,
        "initial_profile": CHARACTER_PROFILE_SCHEMA
    }
}

MOVIE_ANALYSIS_SCHEMA = {
    "type": OBJECT,
    "properties": {
        "overall_setting": {
            "type": OBJECT,
            "properties": {
                "protagonist_adaptation": STRING,
                "horror_core": STRING,
                "scene_atmosphere": STRING,
                "meta_narrative_foreshadowing": {
                    "type": OBJECT,
                    "properties": {
                        "content": STRING,
                        "trigger_scene": NUMBER
                    }
                }
            }
        },
        "character_pool": {
            "type": ARRAY,
            "items": CHARACTER_POOL_ITEM_SCHEMA
        },
        "scenes": {
            "type": ARRAY,
            "items": SCENE_SCHEMA
        }
    }
}

REAL_WORLD_ARC_ANALYSIS_SCHEMA = {
    "type": OBJECT,
    "properties": {
        "arc_title": STRING,
        "overall_goal": STRING,
        "character_pool": {
            "type": ARRAY,
            "items": CHARACTER_POOL_ITEM_SCHEMA
        },
        "scenes": {
            "type": ARRAY,
            "items": SCENE_SCHEMA
        }
    }
}


NEXT_STEP_DECISION_SCHEMA = {
    "type": OBJECT,
    "properties": {
        "decision": STRING,
        "reasoning": STRING,
        "next_chapter_theme": STRING
    }
}

# --- 数据处理 Schema ---
SUMMARY_SCHEMA = {
    "type": OBJECT,
    "properties": {
        "summary": STRING,
        "next_motivation": STRING
    }
}

CHARACTER_IDENTIFICATION_SCHEMA = {
    "type": OBJECT,
    "properties": {
        "characters": {
            "type": ARRAY,
            "items": STRING
        }
    }
}


# --- 议会 Schema ---
PARLIAMENT_MEMBER_SCHEMA = {
    "type": OBJECT,
    "properties": {
        "insights": { "type": ARRAY, "items": STRING },
        "questions": { "type": ARRAY, "items": STRING },
        "improvement_plan": STRING
    }
}

PARLIAMENT_DIRECTOR_SCHEMA = {
    "type": OBJECT,
    "properties": {
        "meeting_summary": STRING,
        "responses_to_members": {
            "type": ARRAY,
            "items": {
                "type": OBJECT,
                "properties": {
                    "member_role": STRING,
                    "response": STRING
                }
            }
        },
        "final_directive": {
            "type": OBJECT,
            "properties": {
                "next_arc_goal": STRING,
                "key_conflict": STRING,
                "emotional_tone": STRING
            }
        }
    }
}

PARLIAMENT_SUMMARY_SCHEMA = {
    "type": OBJECT,
    "properties": {
        "next_arc_goal": STRING,
        "key_conflict": STRING,
        "emotional_tone": STRING,
        "plot_points": { "type": ARRAY, "items": STRING },
        "tool_utilization": STRING
    }
}
