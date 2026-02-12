import React, { useState } from "react";
import {
  StyleSheet,
  Text,
  View,
  ScrollView,
  ActivityIndicator,
  Platform,
  Pressable,
} from "react-native";
import { useQuery } from "@tanstack/react-query";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import Colors from "@/constants/colors";
import SectionHeader from "@/components/SectionHeader";
import LineChart from "@/components/charts/LineChart";
import BarChart from "@/components/charts/BarChart";
import { formatCrore, formatCroreShort, shortYear } from "@/lib/format";

interface DeficitData {
  year: string;
  fiscal: number;
  revenue: number;
  primary: number;
  fiscalPercGDP: number;
}

interface OverviewItem {
  year: string;
  receipts: number;
  expenditure: number;
  fiscalDeficit: number;
  fiscalDeficitPercGDP: number;
  gdp: number;
}

interface BudgetYearData {
  year: string;
  sectors: Array<{ name: string; id: string; allocation: { be: number } }>;
}

export default function TrendsScreen() {
  const insets = useSafeAreaInsets();
  const topPad = Platform.OS === "web" ? 67 : 0;

  const { data: deficitData, isLoading: deficitLoading } = useQuery<DeficitData[]>({
    queryKey: ["/api/budget/deficit"],
  });

  const { data: overviewData, isLoading: overviewLoading } = useQuery<OverviewItem[]>({
    queryKey: ["/api/budget/overview"],
  });

  const { data: allData } = useQuery<BudgetYearData[]>({
    queryKey: ["/api/budget/all"],
  });

  const [selectedSectors, setSelectedSectors] = useState<string[]>(["defence", "health"]);

  const sectorOptions = [
    { id: "defence", name: "Defence" },
    { id: "agriculture", name: "Agriculture" },
    { id: "education", name: "Education" },
    { id: "health", name: "Health" },
    { id: "rural_dev", name: "Rural Dev." },
    { id: "transport", name: "Transport" },
    { id: "social_welfare", name: "Social Welfare" },
    { id: "energy", name: "Energy" },
    { id: "science_tech", name: "Science & Tech" },
  ];

  const sectorColors = [
    Colors.light.chartColors[0],
    Colors.light.chartColors[1],
    Colors.light.chartColors[2],
    Colors.light.chartColors[3],
    Colors.light.chartColors[4],
    Colors.light.chartColors[5],
    Colors.light.chartColors[6],
    Colors.light.chartColors[7],
    Colors.light.chartColors[8],
  ];

  const isLoading = deficitLoading || overviewLoading;

  if (isLoading) {
    return (
      <View style={[styles.loadingContainer, { paddingTop: topPad + insets.top }]}>
        <ActivityIndicator size="large" color={Colors.light.primary} />
      </View>
    );
  }

  const deficitSlice = (deficitData || []).slice(-15);
  const overviewSlice = (overviewData || []).slice(-15);

  const toggleSector = (id: string) => {
    setSelectedSectors((prev) => {
      if (prev.includes(id)) {
        return prev.filter((s) => s !== id);
      }
      if (prev.length >= 4) return prev;
      return [...prev, id];
    });
  };

  const sectorTrendData = selectedSectors.map((sectorId) => {
    const sectorInfo = sectorOptions.find((s) => s.id === sectorId);
    const colorIdx = sectorOptions.findIndex((s) => s.id === sectorId);
    const data = (allData || []).slice(-12).map((year) => {
      const sector = year.sectors.find((s) => s.id === sectorId);
      return sector?.allocation.be || 0;
    });
    return {
      data,
      color: sectorColors[colorIdx % sectorColors.length],
      label: sectorInfo?.name || sectorId,
    };
  });

  const sectorLabels = (allData || []).slice(-12).map((d) => shortYear(d.year));

  return (
    <ScrollView
      style={[styles.container, { paddingTop: topPad }]}
      contentContainerStyle={{ paddingBottom: Platform.OS === "web" ? 34 : 100 }}
      showsVerticalScrollIndicator={false}
    >
      <View style={{ paddingTop: insets.top + 8 }}>
        <View style={styles.pageHeader}>
          <Text style={styles.pageTitle}>Trends</Text>
          <Text style={styles.pageSubtitle}>Multi-year budget analysis</Text>
        </View>

        <SectionHeader title="GDP Growth" subtitle="Nominal GDP over time (BE)" />
        <View style={styles.chartCard}>
          <LineChart
            labels={overviewSlice.map((d) => shortYear(d.year))}
            datasets={[
              {
                data: overviewSlice.map((d) => d.gdp),
                color: Colors.light.primaryLight,
                label: "GDP",
              },
            ]}
            height={220}
            showArea
          />
        </View>

        <SectionHeader title="Fiscal Deficit" subtitle="% of GDP over years (BE)" />
        <View style={styles.chartCard}>
          <LineChart
            labels={deficitSlice.map((d) => shortYear(d.year))}
            datasets={[
              {
                data: deficitSlice.map((d) => d.fiscalPercGDP),
                color: Colors.light.accent,
                label: "Fiscal Deficit % GDP",
              },
            ]}
            height={200}
            showArea
          />
        </View>

        <SectionHeader title="Deficit Components" subtitle="Fiscal, Revenue & Primary Deficit (BE)" />
        <View style={styles.chartCard}>
          <LineChart
            labels={deficitSlice.map((d) => shortYear(d.year))}
            datasets={[
              {
                data: deficitSlice.map((d) => d.fiscal),
                color: Colors.light.danger,
                label: "Fiscal",
              },
              {
                data: deficitSlice.map((d) => d.revenue),
                color: Colors.light.accent,
                label: "Revenue",
              },
              {
                data: deficitSlice.map((d) => Math.max(d.primary, 0)),
                color: Colors.light.success,
                label: "Primary",
              },
            ]}
            height={220}
          />
        </View>

        <SectionHeader title="Sector Comparison" subtitle="Select up to 4 sectors to compare" />
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.sectorChips}
        >
          {sectorOptions.map((s, idx) => {
            const isSelected = selectedSectors.includes(s.id);
            return (
              <Pressable
                key={s.id}
                onPress={() => toggleSector(s.id)}
                style={[
                  styles.sectorChip,
                  isSelected && {
                    backgroundColor: sectorColors[idx % sectorColors.length],
                    borderColor: sectorColors[idx % sectorColors.length],
                  },
                ]}
              >
                <Text style={[styles.sectorChipText, isSelected && styles.sectorChipTextActive]}>
                  {s.name}
                </Text>
              </Pressable>
            );
          })}
        </ScrollView>

        {sectorTrendData.length > 0 && (
          <View style={styles.chartCard}>
            <LineChart
              labels={sectorLabels}
              datasets={sectorTrendData}
              height={240}
              showArea={false}
            />
          </View>
        )}

        <SectionHeader title="Receipts-to-Expenditure Ratio" subtitle="How much of spending is covered by revenue" />
        <View style={styles.chartCard}>
          <BarChart
            data={overviewSlice.map((d) => ({
              label: shortYear(d.year),
              value: d.expenditure > 0 ? (d.receipts / d.expenditure) * 100 : 0,
              color: d.receipts / d.expenditure > 0.7 ? Colors.light.success : Colors.light.danger,
            }))}
            height={200}
            barWidth={22}
            spacing={8}
            formatValue={(v) => `${v.toFixed(0)}%`}
          />
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.light.background,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: Colors.light.background,
  },
  pageHeader: {
    paddingHorizontal: 16,
    paddingBottom: 12,
  },
  pageTitle: {
    fontSize: 24,
    fontFamily: "Inter_800ExtraBold",
    color: Colors.light.text,
  },
  pageSubtitle: {
    fontSize: 13,
    fontFamily: "Inter_400Regular",
    color: Colors.light.textSecondary,
    marginTop: 4,
  },
  chartCard: {
    backgroundColor: Colors.light.surface,
    marginHorizontal: 16,
    borderRadius: 16,
    padding: 16,
    ...Platform.select({
      ios: {
        shadowColor: "#000",
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.06,
        shadowRadius: 8,
      },
      android: { elevation: 2 },
      web: { boxShadow: "0 2px 8px rgba(0,0,0,0.06)" },
    }),
  },
  sectorChips: {
    paddingHorizontal: 16,
    gap: 6,
    marginBottom: 12,
  },
  sectorChip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    backgroundColor: Colors.light.surface,
    borderWidth: 1,
    borderColor: Colors.light.border,
  },
  sectorChipText: {
    fontSize: 12,
    fontFamily: "Inter_500Medium",
    color: Colors.light.textSecondary,
  },
  sectorChipTextActive: {
    color: "#fff",
  },
});
