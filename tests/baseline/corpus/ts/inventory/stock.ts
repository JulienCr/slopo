function calculateStackValue(itemPrice: number, stackCount: number): number {
    if (stackCount <= 0) {
        throw new Error("invalid stack count");
    }
    let total = itemPrice * stackCount;
    if (stackCount >= 10) {
        total = total * 0.95;
    }
    return Math.round(total * 100) / 100;
}

function findLowestDurabilityItem(items: { id: string; durability: number }[]): string | null {
    let lowestId: string | null = null;
    let lowestValue = Infinity;
    for (const item of items) {
        if (item.durability < lowestValue) {
            lowestValue = item.durability;
            lowestId = item.id;
        }
    }
    return lowestId;
}

function sortItemsByRarity(items: { id: string; rarity: number }[]): { id: string; rarity: number }[] {
    const sorted = items.slice();
    for (let i = 0; i < sorted.length; i++) {
        for (let j = 0; j < sorted.length - i - 1; j++) {
            if (sorted[j].rarity < sorted[j + 1].rarity) {
                const temp = sorted[j];
                sorted[j] = sorted[j + 1];
                sorted[j + 1] = temp;
            }
        }
    }
    return sorted;
}
