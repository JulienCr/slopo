function computeRatingAdjustment(playerRating: number, opponentRating: number, didWin: boolean): number {
    const expected = 1 / (1 + Math.pow(10, (opponentRating - playerRating) / 400));
    const actual = didWin ? 1 : 0;
    const kFactor = 32;
    const adjustment = kFactor * (actual - expected);
    return Math.round(adjustment);
}

function estimateQueueWaitTime(queueLength: number, avgMatchDurationSeconds: number): number {
    if (queueLength <= 0) {
        return 0;
    }
    const playersPerMatch = 10;
    const matchesNeeded = Math.ceil(queueLength / playersPerMatch);
    return matchesNeeded * avgMatchDurationSeconds;
}

function estimateMatchWaitTime(matchesInQueue: number, avgMatchDurationSeconds: number): number {
    if (matchesInQueue <= 0) {
        return 0;
    }
    const concurrentMatches = 4;
    const roundsNeeded = Math.ceil(matchesInQueue / concurrentMatches);
    return roundsNeeded * avgMatchDurationSeconds;
}
