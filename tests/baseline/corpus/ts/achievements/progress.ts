function computeCompletionRatio(currentAmount: number, requiredAmount: number): number {
    if (requiredAmount <= 0) {
        throw new Error("invalid required amount");
    }
    let fraction = currentAmount / requiredAmount;
    if (fraction > 1) {
        fraction = 1;
    }
    return Math.round(fraction * 100);
}

function computeStreakBonus(streakDays: number, baseBonus: number): number {
    if (streakDays <= 0) {
        return 0;
    }
    let bonus = baseBonus;
    if (streakDays >= 7) {
        bonus = bonus * 2;
    } else if (streakDays >= 3) {
        bonus = bonus * 1.5;
    }
    return Math.round(bonus);
}
