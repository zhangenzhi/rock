"""
此文件集中定义了项目中所有与Gemini API交互所需的JSON Schema。
这确保了AI返回的数据结构是可预测且被强制约束的。
"""

# 通用类型定义 (保持为字典，方便在properties中使用)
STRING = {"type": "STRING"}
NUMBER = {"type": "NUMBER"}
BOOLEAN = {"type": "BOOLEAN"}
ARRAY = {"type": "ARRAY"}
OBJECT = {"type": "OBJECT"}

# --- 基础 Schema ---
MOVIE_SELECTION_SCHEMA = {
    "type": "OBJECT",
    "properties": { 
        "movie_name": {
            **STRING,
            "description": "为故事主角选择的下一部经典恐怖电影的中文名称。"
        }
    }
}

TOOL_CREATION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "tool_name": {
            **STRING,
            "description": "一个非超自然、来源合理的工具名称。"
        },
        "description": {
            **STRING,
            "description": "对工具外观和在电影世界中来源的详细描述。"
        },
        "potential_use": {
            **STRING,
            "description": "这个普通工具在未来可能发挥的创造性作用，最好能与现实世界的谜团产生潜在联系。"
        }
    }
}

REVIEW_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "review_points": {
            "type": "ARRAY",
            "items": {
                **STRING,
                "description": "一条具体、可操作的修改意见。"
            },
            "description": "一个包含多条尖锐、具体修改意见的列表。"
        }
    }
}

# --- 章节与故事数据 Schema ---
CHARACTER_PROFILE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "background": {
            **STRING,
            "description": "角色的背景故事和核心经历。"
        },
        "motivation": {
            **STRING,
            "description": "驱动角色行动的核心动机和目标。"
        },
        "outlook": {
            **STRING,
            "description": "角色对当前环境和未来的看法与态度。"
        }
    }
}

UPDATED_CHARACTER_PROFILE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "background": {
            **STRING,
            "description": "更新后的角色背景故事，如果角色是主角，可以极其缓慢且隐晦地补充一小部分关于他现实世界背景的细节。"
        },
        "motivation": {
            **STRING,
            "description": "基于最新章节内容更新后的角色核心动机。"
        },
        "outlook": {
            **STRING,
            "description": "更新后的角色对他人和环境的看法。"
        },
        "recent_observations": {
            **STRING,
            "description": "记录角色对本章中遇到的其他具体人物的最新记忆、印象和判断。"
        }
    }
}

CHAPTER_GENERATION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "title": {
            **STRING,
            "description": "本章的标题，应与场景的核心事件（subtitle）一致。"
        },
        "pov_character": {
            **STRING,
            "description": "本章的叙事视点角色的确切名称。"
        },
        "paragraphs": {
            "type": "ARRAY",
            "items": {
                **STRING,
                "description": "一个段落的文本。段落应简短，以优化移动端阅读体验，并全力渲染预设的核心情绪锚点。"
            },
            "description": "包含本章所有正文段落的数组。"
        }
    }
}

# --- 规划与决策 Schema ---
SCENE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "scene_number": {
            **NUMBER,
            "description": "场景的顺序编号。"
        },
        "day": {
            **NUMBER,
            "description": "故事发生的天数。"
        },
        "part_of_day": {
            **STRING,
            "description": "场景发生的时间段，如“白天”、“黄昏”、“夜晚”。"
        },
        "subtitle": {
            **STRING,
            "description": "场景的副标题，概括核心事件。"
        },
        "synopsis": {
            **STRING,
            "description": "场景的剧情梗概，需明确指出角色之间需要进行的关键互动或合作。"
        },
        "pov_character": {
            **STRING,
            "description": "此场景的核心叙事视点角色，必须是主角或已在角色池中定义的人物。"
        },
        "emotion_anchor": {
            **STRING,
            "description": "此场景需要传达给读者的核心情绪，例如“紧张”、“绝望”、“短暂的温馨”。"
        }
    }
}

CHARACTER_POOL_ITEM_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "name": {
            **STRING,
            "description": "NPC的姓名。"
        },
        "personality": {
            **STRING,
            "description": "NPC的性格特点。"
        },
        "function": {
            **STRING,
            "description": "该NPC在剧情中扮演的具体作用，例如“提供线索”、“制造冲突”或“作为主角的盟友”。"
        },
        "initial_profile": {
            **CHARACTER_PROFILE_SCHEMA,
            "description": "一份详细的初始角色侧写，以便写手理解其行为逻辑。"
        }
    }
}

MOVIE_ANALYSIS_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "overall_setting": {
            "type": "OBJECT",
            "properties": {
                "protagonist_adaptation": {
                    **STRING,
                    "description": "改编电影的核心情节，使其符合主角“江浩”作为中国普通待业青年的身份。为他被卷入核心事件设计一个原创且合理的动机。"
                },
                "horror_core": {
                    **STRING,
                    "description": "电影的核心恐怖来源是什么？是物理威胁、心理压迫还是未知恐惧？"
                },
                "scene_atmosphere": {
                    **STRING,
                    "description": "描述这个世界的主要场景和能激发读者爽点的整体氛围。"
                },
                "meta_narrative_foreshadowing": {
                    "type": "OBJECT",
                    "properties": {
                        "content": {
                            **STRING,
                            "description": "构思一种方式，让角色偶尔能感觉到一种被无形之手操纵的诡异感，作为隐藏伏笔。此手法必须非常谨慎、隐晦地使用。"
                        },
                        "trigger_scene": {
                            **NUMBER,
                            "description": "指定该伏笔被揭示或加强的高潮场景的编号（scene_number）。"
                        }
                    }
                }
            }
        },
        "character_pool": {
            "type": "ARRAY",
            "items": CHARACTER_POOL_ITEM_SCHEMA,
            "description": "本章节中将出现的所有重要NPC列表。"
        },
        "scenes": {
            "type": "ARRAY",
            "items": SCENE_SCHEMA,
            "description": "包含10-15个场景的完整故事弧，需注意叙事节奏，做到张弛有度。"
        }
    }
}

REAL_WORLD_ARC_ANALYSIS_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "arc_title": {
            **STRING,
            "description": "为这个现实世界迷你章节起一个引人入胜的标题，例如：'失落的记忆碎片'。"
        },
        "overall_goal": {
            **STRING,
            "description": "明确这个章节的核心调查目标，例如：'调查从电影世界带回的物品的来源'。"
        },
        "character_pool": {
            "type": "ARRAY",
            "items": CHARACTER_POOL_ITEM_SCHEMA,
            "description": "在本章节中引入或深化的现实世界角色。"
        },
        "scenes": {
            "type": "ARRAY",
            "items": SCENE_SCHEMA,
            "description": "包含3-5个场景的迷你章节，旨在挖掘线索、深化角色关系并制造悬念。"
        }
    }
}


NEXT_STEP_DECISION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "decision": {
            **STRING,
            "description": "决策结果，必须是 'REAL_WORLD' 或 'MOVIE_WORLD'。"
        },
        "reasoning": {
            **STRING,
            "description": "陈述做出此决策的叙事逻辑，例如：'主角刚获得的关键物品上发现了新线索，必须先在现实中追查。'"
        },
        "next_chapter_theme": {
            **STRING,
            "description": "为下一章拟定一个简洁的核心主题或副标题。"
        }
    }
}

# --- 数据处理 Schema ---
SUMMARY_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "summary": {
            **STRING,
            "description": "一份简洁的、聚焦于当前尚未解决的关键冲突和新谜团的摘要。"
        },
        "next_motivation": {
            **STRING,
            "description": "明确指出主角或关键人物接下来最可能的目标或行动方向。"
        }
    }
}

CHARACTER_IDENTIFICATION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "characters": {
            "type": "ARRAY",
            "items": STRING,
            "description": "故事摘要中提及的所有主要角色的名字列表。"
        }
    }
}


# --- 议会 Schema ---
PARLIAMENT_MEMBER_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "insights": {
            "type": "ARRAY",
            "items": STRING,
            "description": "基于专属资料分析出的1-2个关键洞察或问题点。"
        },
        "questions": {
            "type": "ARRAY",
            "items": STRING,
            "description": "对未来剧情走向的2-3个核心问题。"
        },
        "improvement_plan": {
            **STRING,
            "description": "阐述该角色在下一阶段的工作优化方向，例如：'作为心理分析师，我将更深入地挖掘角色在压力下的心理矛盾。'"
        }
    }
}

PARLIAMENT_DIRECTOR_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "meeting_summary": {
            **STRING,
            "description": "对整个会议所有成员发言的总体概括。"
        },
        "responses_to_members": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "member_role": STRING,
                    "response": STRING
                }
            },
            "description": "对每个议会成员提出的具体问题的回应和看法。"
        },
        "final_directive": {
            "type": "OBJECT",
            "properties": {
                "next_arc_goal": STRING,
                "key_conflict": STRING,
                "emotional_tone": STRING
            },
            "description": "综合所有观点后，为下一阶段现实世界主线故事制定的明确方向。"
        }
    }
}

PARLIAMENT_SUMMARY_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "next_arc_goal": {
            **STRING,
            "description": "下一个现实世界章节的核心目标。"
        },
        "key_conflict": {
            **STRING,
            "description": "主角将面临的关键冲突或谜团。"
        },
        "emotional_tone": {
            **STRING,
            "description": "故事的情感基调。"
        },
        "plot_points": {
            "type": "ARRAY",
            "items": STRING,
            "description": "包含2-3个推进核心目标的具体关键情节点。"
        },
        "tool_utilization": {
            **STRING,
            "description": "描述应如何创造性地使用主角最近获得的工具来解决问题或发现线索。"
        }
    }
}

