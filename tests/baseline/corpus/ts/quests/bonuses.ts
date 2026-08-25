function computeGoldBonus(baseGold: number, difficultyLevel: number): number {
    if (difficultyLevel <= 0) {
        throw new Error("invalid difficulty level");
    }
    let bonus = baseGold * (difficultyLevel * 0.1);
    if (bonus > baseGold) {
        bonus = baseGold;
    }
    return Math.round(bonus);
}

function computeItemDropChance(playerLuck: number, baseChance: number): number {
    let chance = baseChance + playerLuck * 0.01;
    if (chance > 0.95) {
        chance = 0.95;
    }
    if (chance < 0) {
        chance = 0;
    }
    return Math.round(chance * 1000) / 1000;
}
