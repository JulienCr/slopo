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

function findWeakestArmorSlot(items: { id: string; armor: number }[]): string | null {
    let weakestId: string | null = null;
    let weakestValue = Infinity;
    for (const item of items) {
        if (item.armor < weakestValue) {
            weakestValue = item.armor;
            weakestId = item.id;
        }
    }
    return weakestId;
}

function equipItemToSlot(
    loadout: Record<string, string | null>,
    slot: string,
    itemId: string
): Record<string, string | null> {
    if (!(slot in loadout)) {
        throw new Error("unknown slot: " + slot);
    }
    const updated: Record<string, string | null> = {};
    for (const key in loadout) {
        updated[key] = loadout[key];
    }
    updated[slot] = itemId;
    return updated;
}

function countEquippedSlots(loadout: Record<string, string | null>): number {
    let count = 0;
    for (const slot in loadout) {
        if (loadout[slot] !== null) {
            count += 1;
        }
    }
    return count;
}

function countEmptySlots(loadout: Record<string, string | null>): number {
    let count = 0;
    for (const slot in loadout) {
        if (loadout[slot] === null) {
            count += 1;
        }
    }
    return count;
}
