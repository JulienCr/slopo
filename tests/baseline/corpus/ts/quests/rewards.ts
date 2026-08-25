function clampRatingDelta(delta: number, maxDelta: number): number {
    if (delta > maxDelta) {
        return maxDelta;
    }
    if (delta < -maxDelta) {
        return -maxDelta;
    }
    return delta;
}

function calculateBonusGold(baseGold: number, questDifficulty: number): number {
    if (questDifficulty <= 0) {
        throw new Error("invalid quest difficulty");
    }
    let bonus = baseGold * (questDifficulty * 0.1);
    if (bonus > baseGold) {
        bonus = baseGold;
    }
    return Math.round(bonus);
}

function calculateBonusExperience(baseExperience: number, questDifficulty: number): number {
    if (questDifficulty <= 0) {
        throw new Error("invalid quest difficulty");
    }
    let bonus = baseExperience * (questDifficulty * 0.15);
    if (bonus > baseExperience) {
        bonus = baseExperience;
    }
    return Math.round(bonus);
}
