function computeEloDelta(playerRating: number, opponentRating: number, didWin: boolean): number {
    const expected = 1 / (1 + Math.pow(10, (opponentRating - playerRating) / 400));
    const actual = didWin ? 1 : 0;
    const kFactor = 32;
    const delta = kFactor * (actual - expected);
    return Math.round(delta);
}

function clampRatingDelta(delta: number, maxDelta: number): number {
    if (delta > maxDelta) {
        return maxDelta;
    }
    if (delta < -maxDelta) {
        return -maxDelta;
    }
    return delta;
}

function computeSkillTier(rating: number): string {
    if (rating >= 2400) {
        return "master";
    } else if (rating >= 2000) {
        return "diamond";
    } else if (rating >= 1600) {
        return "platinum";
    } else if (rating >= 1200) {
        return "gold";
    }
    return "silver";
}
