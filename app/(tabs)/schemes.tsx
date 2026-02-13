import React, { useState, useMemo } from "react";
import {
  StyleSheet,
  Text,
  View,
  FlatList,
  ActivityIndicator,
  Platform,
  Pressable,
  TextInput,
} from "react-native";
import { useQuery } from "@tanstack/react-query";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import Colors from "@/constants/colors";
import { formatCrore } from "@/lib/format";

interface SchemeItem {
  id: string;
  name: string;
  sectorId: string;
  sectorName: string;
  type: "sector" | "css";
  firstYear: string;
  lastYear: string;
  latestBE: number;
  latestYear: string;
  isActive: boolean;
  peakBE: number;
  peakYear: string;
}

type FilterType = "all" | "active" | "discontinued";
type SortType = "allocation" | "name" | "newest" | "oldest";

const sectorColors: Record<string, string> = {
  defence: "#1B4F72",
  agriculture: "#27AE60",
  education: "#8E44AD",
  health: "#E74C3C",
  rural_dev: "#F39C12",
  urban_dev: "#3498DB",
  energy: "#E67E22",
  transport: "#2C3E50",
  social_welfare: "#16A085",
  science_tech: "#9B59B6",
  css: "#2980B9",
};

export default function SchemesScreen() {
  const insets = useSafeAreaInsets();
  const topPad = Platform.OS === "web" ? 67 : 0;

  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState<FilterType>("all");
  const [sortType, setSortType] = useState<SortType>("allocation");
  const [selectedSector, setSelectedSector] = useState<string | null>(null);

  const { data: schemes, isLoading } = useQuery<SchemeItem[]>({
    queryKey: ["/api/budget/schemes/directory"],
  });

  const sectors = useMemo(() => {
    if (!schemes) return [];
    const sectorSet = new Map<string, string>();
    for (const s of schemes) {
      if (!sectorSet.has(s.sectorId)) {
        sectorSet.set(s.sectorId, s.sectorName);
      }
    }
    return Array.from(sectorSet.entries()).map(([id, name]) => ({ id, name }));
  }, [schemes]);

  const filtered = useMemo(() => {
    if (!schemes) return [];
    let result = [...schemes];

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (s) =>
          s.name.toLowerCase().includes(q) ||
          s.sectorName.toLowerCase().includes(q) ||
          s.id.toLowerCase().includes(q)
      );
    }

    if (filterType === "active") result = result.filter((s) => s.isActive);
    if (filterType === "discontinued") result = result.filter((s) => !s.isActive);
    if (selectedSector) result = result.filter((s) => s.sectorId === selectedSector);

    switch (sortType) {
      case "allocation":
        result.sort((a, b) => b.latestBE - a.latestBE);
        break;
      case "name":
        result.sort((a, b) => a.name.localeCompare(b.name));
        break;
      case "newest":
        result.sort((a, b) => b.firstYear.localeCompare(a.firstYear));
        break;
      case "oldest":
        result.sort((a, b) => a.firstYear.localeCompare(b.firstYear));
        break;
    }
    return result;
  }, [schemes, searchQuery, filterType, sortType, selectedSector]);

  const activeCount = schemes?.filter((s) => s.isActive).length || 0;
  const totalCount = schemes?.length || 0;
  const discontinuedCount = totalCount - activeCount;

  const handleSchemePress = (scheme: SchemeItem) => {
    router.push({
      pathname: "/scheme/[id]",
      params: { id: scheme.id, name: scheme.name },
    });
  };

  const renderSchemeItem = ({ item }: { item: SchemeItem }) => {
    const color = sectorColors[item.sectorId] || Colors.light.primary;
    return (
      <Pressable
        style={styles.schemeItem}
        onPress={() => handleSchemePress(item)}
      >
        <View style={[styles.schemeDot, { backgroundColor: color }]} />
        <View style={styles.schemeInfo}>
          <View style={styles.schemeRow}>
            <Text style={styles.schemeName} numberOfLines={1}>{item.name}</Text>
            {!item.isActive && (
              <View style={styles.discontinuedBadge}>
                <Text style={styles.discontinuedText}>Ended</Text>
              </View>
            )}
          </View>
          <View style={styles.schemeMeta}>
            <Text style={styles.schemeSector}>{item.sectorName}</Text>
            <Text style={styles.schemeDivider}>|</Text>
            <Text style={styles.schemeYears}>{item.firstYear} - {item.isActive ? "Present" : item.lastYear}</Text>
          </View>
          <View style={styles.schemeValues}>
            <Text style={styles.schemeAllocation}>{formatCrore(item.latestBE)}</Text>
            <Text style={styles.schemeLabel}>{item.isActive ? `BE ${item.latestYear}` : `Peak: ${formatCrore(item.peakBE)} (${item.peakYear})`}</Text>
          </View>
        </View>
        <Ionicons name="chevron-forward" size={16} color={Colors.light.textSecondary} />
      </Pressable>
    );
  };

  if (isLoading) {
    return (
      <View style={[styles.loadingContainer, { paddingTop: topPad + insets.top }]}>
        <ActivityIndicator size="large" color={Colors.light.primary} />
      </View>
    );
  }

  return (
    <View style={[styles.container, { paddingTop: topPad + insets.top + 8 }]}>
      <View style={styles.pageHeader}>
        <Text style={styles.pageTitle}>All Schemes</Text>
        <Text style={styles.pageSubtitle}>{filtered.length} of {totalCount} schemes ({activeCount} active, {discontinuedCount} past)</Text>
      </View>

      <View style={styles.searchContainer}>
        <Ionicons name="search" size={18} color={Colors.light.textSecondary} style={styles.searchIcon} />
        <TextInput
          style={styles.searchInput}
          placeholder="Search schemes..."
          placeholderTextColor={Colors.light.textSecondary}
          value={searchQuery}
          onChangeText={setSearchQuery}
        />
        {searchQuery.length > 0 && (
          <Pressable onPress={() => setSearchQuery("")}>
            <Ionicons name="close-circle" size={18} color={Colors.light.textSecondary} />
          </Pressable>
        )}
      </View>

      <View style={styles.filtersRow}>
        {(["all", "active", "discontinued"] as FilterType[]).map((f) => (
          <Pressable
            key={f}
            onPress={() => setFilterType(f)}
            style={[styles.filterChip, filterType === f && styles.filterChipActive]}
          >
            <Text style={[styles.filterText, filterType === f && styles.filterTextActive]}>
              {f === "all" ? "All" : f === "active" ? "Active" : "Past"}
            </Text>
          </Pressable>
        ))}
        <View style={styles.sortContainer}>
          <Pressable
            onPress={() => {
              const sortOrder: SortType[] = ["allocation", "name", "newest", "oldest"];
              const idx = sortOrder.indexOf(sortType);
              setSortType(sortOrder[(idx + 1) % sortOrder.length]);
            }}
            style={styles.sortButton}
          >
            <Ionicons name="swap-vertical" size={14} color={Colors.light.primary} />
            <Text style={styles.sortText}>
              {sortType === "allocation" ? "By Amount" : sortType === "name" ? "A-Z" : sortType === "newest" ? "Newest" : "Oldest"}
            </Text>
          </Pressable>
        </View>
      </View>

      <FlatList
        horizontal
        data={[{ id: null as string | null, name: "All Sectors" }, ...sectors]}
        keyExtractor={(item) => item.id || "all"}
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.sectorChips}
        renderItem={({ item: s }) => (
          <Pressable
            onPress={() => setSelectedSector(s.id === selectedSector ? null : s.id)}
            style={[
              styles.sectorChip,
              (s.id === selectedSector || (s.id === null && selectedSector === null)) && styles.sectorChipActive,
            ]}
          >
            {s.id && <View style={[styles.sectorDot, { backgroundColor: sectorColors[s.id] || Colors.light.primary }]} />}
            <Text style={[
              styles.sectorChipText,
              (s.id === selectedSector || (s.id === null && selectedSector === null)) && styles.sectorChipTextActive,
            ]}>
              {s.name}
            </Text>
          </Pressable>
        )}
      />

      <FlatList
        data={filtered}
        keyExtractor={(item) => item.id}
        renderItem={renderSchemeItem}
        contentContainerStyle={{ paddingBottom: Platform.OS === "web" ? 34 : 100, paddingHorizontal: 16 }}
        showsVerticalScrollIndicator={false}
        scrollEnabled={filtered.length > 0}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Ionicons name="search" size={48} color={Colors.light.border} />
            <Text style={styles.emptyText}>No schemes found</Text>
            <Text style={styles.emptySubtext}>Try adjusting your filters</Text>
          </View>
        }
        ListHeaderComponent={
          <Text style={styles.resultCount}>{filtered.length} schemes</Text>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.light.background },
  loadingContainer: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: Colors.light.background },
  pageHeader: { paddingHorizontal: 16, paddingBottom: 12 },
  pageTitle: { fontSize: 24, fontFamily: "Inter_800ExtraBold", color: Colors.light.text },
  pageSubtitle: { fontSize: 13, fontFamily: "Inter_400Regular", color: Colors.light.textSecondary, marginTop: 4 },
  searchContainer: {
    flexDirection: "row",
    alignItems: "center",
    marginHorizontal: 16,
    backgroundColor: Colors.light.surface,
    borderRadius: 12,
    paddingHorizontal: 12,
    height: 42,
    borderWidth: 1,
    borderColor: Colors.light.border,
    marginBottom: 10,
  },
  searchIcon: { marginRight: 8 },
  searchInput: {
    flex: 1,
    fontSize: 14,
    fontFamily: "Inter_400Regular",
    color: Colors.light.text,
  },
  filtersRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    gap: 6,
    marginBottom: 8,
  },
  filterChip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    backgroundColor: Colors.light.surface,
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  filterChipActive: {
    backgroundColor: Colors.light.primary,
    borderColor: Colors.light.primary,
  },
  filterText: { fontSize: 12, fontFamily: "Inter_500Medium", color: Colors.light.textSecondary },
  filterTextActive: { color: "#fff" },
  sortContainer: { flex: 1, alignItems: "flex-end" },
  sortButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 16,
    backgroundColor: Colors.light.primary + "10",
  },
  sortText: { fontSize: 11, fontFamily: "Inter_500Medium", color: Colors.light.primary },
  sectorChips: { paddingHorizontal: 16, gap: 6, paddingBottom: 8 },
  sectorChip: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 14,
    backgroundColor: Colors.light.surface,
    borderWidth: 1,
    borderColor: Colors.light.border,
    gap: 5,
  },
  sectorChipActive: {
    backgroundColor: Colors.light.primary + "15",
    borderColor: Colors.light.primary,
  },
  sectorDot: { width: 8, height: 8, borderRadius: 4 },
  sectorChipText: { fontSize: 11, fontFamily: "Inter_500Medium", color: Colors.light.textSecondary },
  sectorChipTextActive: { color: Colors.light.primary },
  resultCount: {
    fontSize: 12,
    fontFamily: "Inter_500Medium",
    color: Colors.light.textSecondary,
    marginBottom: 8,
  },
  schemeItem: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: Colors.light.surface,
    borderRadius: 14,
    padding: 14,
    marginBottom: 8,
    gap: 10,
    ...Platform.select({
      ios: { shadowColor: "#000", shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.04, shadowRadius: 4 },
      android: { elevation: 1 },
      web: { boxShadow: "0 1px 4px rgba(0,0,0,0.04)" },
    }),
  },
  schemeDot: { width: 10, height: 10, borderRadius: 5 },
  schemeInfo: { flex: 1, gap: 3 },
  schemeRow: { flexDirection: "row", alignItems: "center", gap: 6 },
  schemeName: { fontSize: 14, fontFamily: "Inter_600SemiBold", color: Colors.light.text, flex: 1 },
  discontinuedBadge: {
    backgroundColor: Colors.light.textSecondary + "20",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  discontinuedText: { fontSize: 9, fontFamily: "Inter_500Medium", color: Colors.light.textSecondary },
  schemeMeta: { flexDirection: "row", alignItems: "center", gap: 4 },
  schemeSector: { fontSize: 11, fontFamily: "Inter_400Regular", color: Colors.light.primary },
  schemeDivider: { fontSize: 10, color: Colors.light.border },
  schemeYears: { fontSize: 11, fontFamily: "Inter_400Regular", color: Colors.light.textSecondary },
  schemeValues: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 2 },
  schemeAllocation: { fontSize: 13, fontFamily: "Inter_700Bold", color: Colors.light.text },
  schemeLabel: { fontSize: 10, fontFamily: "Inter_400Regular", color: Colors.light.textSecondary },
  emptyContainer: { alignItems: "center", paddingTop: 60, gap: 8 },
  emptyText: { fontSize: 16, fontFamily: "Inter_600SemiBold", color: Colors.light.textSecondary },
  emptySubtext: { fontSize: 13, fontFamily: "Inter_400Regular", color: Colors.light.textSecondary },
});
