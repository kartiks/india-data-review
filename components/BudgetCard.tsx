import React from "react";
import { View, Text, StyleSheet, Pressable, Platform } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import Colors from "@/constants/colors";

interface BudgetCardProps {
  title: string;
  value: string;
  subtitle?: string;
  icon?: keyof typeof Ionicons.glyphMap;
  iconColor?: string;
  onPress?: () => void;
  growth?: number;
  children?: React.ReactNode;
}

export default function BudgetCard({
  title,
  value,
  subtitle,
  icon,
  iconColor = Colors.light.primary,
  onPress,
  growth,
  children,
}: BudgetCardProps) {
  const Wrapper = onPress ? Pressable : View;
  return (
    <Wrapper
      style={({ pressed }: any) => [
        styles.card,
        onPress && pressed && styles.cardPressed,
      ]}
      onPress={onPress}
    >
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          {icon && (
            <View style={[styles.iconContainer, { backgroundColor: iconColor + "15" }]}>
              <Ionicons name={icon} size={18} color={iconColor} />
            </View>
          )}
          <Text style={styles.title} numberOfLines={1}>{title}</Text>
        </View>
        {onPress && (
          <Ionicons name="chevron-forward" size={16} color={Colors.light.textSecondary} />
        )}
      </View>
      <View style={styles.valueRow}>
        <Text style={styles.value}>{value}</Text>
        {growth !== undefined && growth !== 0 && (
          <View style={[styles.growthBadge, { backgroundColor: growth > 0 ? Colors.light.success + "15" : Colors.light.danger + "15" }]}>
            <Ionicons
              name={growth > 0 ? "trending-up" : "trending-down"}
              size={12}
              color={growth > 0 ? Colors.light.success : Colors.light.danger}
            />
            <Text style={[styles.growthText, { color: growth > 0 ? Colors.light.success : Colors.light.danger }]}>
              {Math.abs(growth).toFixed(1)}%
            </Text>
          </View>
        )}
      </View>
      {subtitle && <Text style={styles.subtitle}>{subtitle}</Text>}
      {children}
    </Wrapper>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.light.surface,
    borderRadius: 16,
    padding: 16,
    ...Platform.select({
      ios: {
        shadowColor: "#000",
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.06,
        shadowRadius: 8,
      },
      android: {
        elevation: 2,
      },
      web: {
        boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
      },
    }),
  },
  cardPressed: {
    opacity: 0.9,
    transform: [{ scale: 0.98 }],
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  headerLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    flex: 1,
  },
  iconContainer: {
    width: 32,
    height: 32,
    borderRadius: 10,
    justifyContent: "center",
    alignItems: "center",
  },
  title: {
    fontSize: 13,
    fontFamily: "Inter_500Medium",
    color: Colors.light.textSecondary,
    flex: 1,
  },
  valueRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  value: {
    fontSize: 22,
    fontFamily: "Inter_700Bold",
    color: Colors.light.text,
  },
  growthBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 2,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 8,
  },
  growthText: {
    fontSize: 11,
    fontFamily: "Inter_600SemiBold",
  },
  subtitle: {
    fontSize: 11,
    fontFamily: "Inter_400Regular",
    color: Colors.light.textSecondary,
    marginTop: 2,
  },
});
