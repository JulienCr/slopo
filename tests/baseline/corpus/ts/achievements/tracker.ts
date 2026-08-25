function calculateProgressPercent(currentValue: number, targetValue: number): number {
    if (targetValue <= 0) {
        throw new Error("invalid target value");
    }
    let ratio = currentValue / targetValue;
    if (ratio > 1) {
        ratio = 1;
    }
    return Math.round(ratio * 100);
}

function calculateMasteryPercent(currentLevel: number, maxLevel: number): number {
    if (maxLevel <= 0) {
        throw new Error("invalid max level");
    }
    let ratio = currentLevel / maxLevel;
    if (ratio > 1) {
        ratio = 1;
    }
    return Math.round(ratio * 100);
}

function recordAchievementUnlock(
    unlocked: Record<string, boolean>,
    achievementId: string
): Record<string, boolean> {
    const updated: Record<string, boolean> = {};
    for (const key in unlocked) {
        updated[key] = unlocked[key];
    }
    updated[achievementId] = true;
    return updated;
}
