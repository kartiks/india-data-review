import React from "react";
import { View, Text, StyleSheet, Pressable } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import Colors from "@/constants/colors";

interface SectionHeaderProps {
  title: string;
  subtitle?: string;
  onPress?: () => void;
  actionLabel?: string;
}

export default function SectionHeader({ title, subtitle, onPress, actionLabel }: SectionHeaderProps) {
  return (
    <View style={styles.container}>
      <View style={styles.textContainer}>
        <Text style={styles.title}>{title}</Text>
        {subtitle && <Text style={styles.subtitle}>{subtitle}</Text>}
      </View>
      {onPress && (
        <Pressable onPress={onPress} style={styles.action}>
          <Text style={styles.actionText}>{actionLabel || "View All"}</Text>
          <Ionicons name="chevron-forward" size={14} color={Colors.light.primaryLight} />
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-end",
    paddingHorizontal: 16,
    marginBottom: 8,
    marginTop: 16,
  },
  textContainer: {
    flex: 1,
  },
  title: {
    fontSize: 18,
    fontFamily: "Inter_700Bold",
    color: Colors.light.text,
  },
  subtitle: {
    fontSize: 12,
    fontFamily: "Inter_400Regular",
    color: Colors.light.textSecondary,
    marginTop: 2,
  },
  action: {
    flexDirection: "row",
    alignItems: "center",
    gap: 2,
  },
  actionText: {
    fontSize: 13,
    fontFamily: "Inter_500Medium",
    color: Colors.light.primaryLight,
  },
});
